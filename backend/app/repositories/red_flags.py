"""Red-flag persistence and reads (Phase 7e, FR-RF-006..010, ADR-0043)."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Company, Filing, IngestionRun, RedFlag

SCAN_SOURCE = "red_flags"  # ingestion_runs.source of a detection pass

FlagKey = tuple[str, int, str | None]  # (rule_key, filing_id, paragraph_id)


def first_detections(session: Session, company_id: int) -> dict[FlagKey, datetime]:
    """When each event was first detected, under any taxonomy version."""
    rows = session.execute(
        select(
            RedFlag.rule_key, RedFlag.filing_id, RedFlag.paragraph_id, func.min(RedFlag.detected_at)
        )
        .where(RedFlag.company_id == company_id)
        .group_by(RedFlag.rule_key, RedFlag.filing_id, RedFlag.paragraph_id)
    )
    return {(rule, filing, paragraph): at for rule, filing, paragraph, at in rows}


def insert_flags(session: Session, rows: Sequence[dict[str, Any]]) -> int:
    """Insert new flags; an event already stored under this taxonomy version is left alone."""
    if not rows:
        return 0
    result = session.execute(
        insert(RedFlag).values(list(rows)).on_conflict_do_nothing().returning(RedFlag.id)
    )
    return len(result.all())


def latest_flags(
    session: Session,
    *,
    company_ids: Collection[int],
    taxonomy_version: str,
    since: date | None = None,
    severities: Collection[str] | None = None,
    rule_keys: Collection[str] | None = None,
    detected_after: datetime | None = None,
    detected_until: datetime | None = None,
    limit: int | None = None,
) -> list[tuple[RedFlag, Filing, str]]:
    """Flags of one taxonomy version, newest event first, with their filing and ticker."""
    conditions = [
        RedFlag.company_id.in_(company_ids),
        RedFlag.taxonomy_version == taxonomy_version,
    ]
    if since is not None:
        conditions.append(RedFlag.event_date >= since)
    if severities is not None:
        conditions.append(RedFlag.severity.in_(severities))
    if rule_keys:
        conditions.append(RedFlag.rule_key.in_(rule_keys))
    if detected_after is not None:
        conditions.append(RedFlag.detected_at > detected_after)
    if detected_until is not None:
        conditions.append(RedFlag.detected_at <= detected_until)
    query = (
        select(RedFlag, Filing, Company.ticker)
        .join(Filing, Filing.id == RedFlag.filing_id)
        .join(Company, Company.id == RedFlag.company_id)
        .where(*conditions)
        .order_by(RedFlag.event_date.desc().nulls_last(), RedFlag.id.desc())
    )
    if limit is not None:
        query = query.limit(limit)
    return [(flag, filing, ticker) for flag, filing, ticker in session.execute(query)]


def by_source(
    session: Session, *, ticker: str, rule_key: str, accession: str, taxonomy_version: str
) -> tuple[RedFlag, Filing] | None:
    """The flag behind `redflag:{ticker}:{rule_key}:{accession}` (current taxonomy version)."""
    row = session.execute(
        select(RedFlag, Filing)
        .join(Filing, Filing.id == RedFlag.filing_id)
        .join(Company, Company.id == RedFlag.company_id)
        .where(
            Company.ticker == ticker.upper(),
            RedFlag.rule_key == rule_key,
            Filing.accession_number == accession,
            RedFlag.taxonomy_version == taxonomy_version,
        )
        .order_by(RedFlag.id)
        .limit(1)
    ).first()
    return (row[0], row[1]) if row else None


def last_scanned_at(session: Session, company_ids: Collection[int]) -> datetime | None:
    """The oldest of the companies' latest successful scans: everything is scanned through it.
    None when any company has never been scanned."""
    latest: dict[int, datetime] = {
        cid: at
        for cid, at in session.execute(
            select(IngestionRun.company_id, func.max(IngestionRun.ended_at))
            .where(
                IngestionRun.source == SCAN_SOURCE,
                IngestionRun.status == "success",
                IngestionRun.company_id.in_(company_ids),
            )
            .group_by(IngestionRun.company_id)
        )
        if cid is not None and at is not None
    }
    if not company_ids or any(cid not in latest for cid in company_ids):
        return None
    return min(latest[cid] for cid in company_ids)
