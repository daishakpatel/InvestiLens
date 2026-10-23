"""Red-flag panel endpoints (Phase 7e, FR-RF-009/010, ADR-0043).

Read-only over `red_flags`, newest event first, current taxonomy version only. An empty list is
explicit and carries the last scan time, so the UI can say "scanned through <date>, nothing
reported" instead of showing a blank panel.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.companies import _resolve
from app.api.deps import get_current_user_id
from app.db import get_db
from app.models import Filing, RedFlag
from app.redflags import taxonomy
from app.repositories import red_flags as repo
from app.repositories import watchlists as watchlist_repo
from app.schemas.red_flags import RedFlagFiling, RedFlagItem, RedFlagsResponse, Severity

router = APIRouter(tags=["Red flags"])

_DB = Depends(get_db, scope="function")
_USER = Depends(get_current_user_id)
_LIMIT = Query(default=50, ge=1, le=200)
_SINCE = Query(default=None, description="Only events filed on or after this date")
_SEVERITY = Query(default=None, description="Minimum severity: info < warning < critical")


def to_item(flag: RedFlag, filing: Filing, ticker: str) -> RedFlagItem:
    rule = taxonomy.RULES_BY_KEY[flag.rule_key]
    return RedFlagItem(
        source_id=taxonomy.source_id(ticker, flag.rule_key, filing.accession_number),
        ticker=ticker,
        rule_key=flag.rule_key,
        label=rule.label,
        severity=rule.severity,
        explanation=rule.explanation,
        rule_source=rule.source,
        event_date=flag.event_date.isoformat() if flag.event_date else None,
        snippet=flag.snippet,
        filing=RedFlagFiling(
            id=filing.id,
            filing_type=filing.filing_type,
            accession_number=filing.accession_number,
            filing_date=filing.filing_date.isoformat() if filing.filing_date else None,
            url=filing.primary_document_url or filing.source_url,
        ),
        details=flag.payload or {},
    )


def _response(
    db: Session, company_ids: list[int], since: date | None, severity: Severity | None, limit: int
) -> RedFlagsResponse:
    rows = repo.latest_flags(
        db,
        company_ids=company_ids,
        taxonomy_version=taxonomy.TAXONOMY_VERSION,
        since=since,
        severities=taxonomy.severities_at_least(severity),
        limit=limit,
    )
    return RedFlagsResponse(
        # A flag from a rule this build no longer defines is left out, not shown unlabelled.
        items=[
            to_item(f, filing, t) for f, filing, t in rows if f.rule_key in taxonomy.RULES_BY_KEY
        ],
        last_scanned_at=repo.last_scanned_at(db, company_ids) if company_ids else None,
        taxonomy_version=taxonomy.TAXONOMY_VERSION,
    )


@router.get("/companies/{ticker}/red-flags", response_model=RedFlagsResponse)
def company_red_flags(
    ticker: str,
    since: date | None = _SINCE,
    severity: Severity | None = _SEVERITY,
    limit: int = _LIMIT,
    db: Session = _DB,
) -> RedFlagsResponse:
    """Reported events for one company, newest first (FR-RF-009)."""
    company = _resolve(db, ticker)
    return _response(db, [company.id], since, severity, limit)


@router.get("/red-flags", response_model=RedFlagsResponse)
def watchlist_red_flags(
    watchlist: bool = Query(description="Must be true: the feed covers the caller's watchlist"),
    since: date | None = _SINCE,
    severity: Severity | None = _SEVERITY,
    limit: int = _LIMIT,
    db: Session = _DB,
    user_id: int = _USER,
) -> RedFlagsResponse:
    """Reported events across every company on the caller's watchlists (FR-RF-009)."""
    if not watchlist:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "only the watchlist feed exists: watchlist=true"
        )
    company_ids = watchlist_repo.company_ids_for_user(db, user_id=user_id)
    return _response(db, company_ids, since, severity, limit)
