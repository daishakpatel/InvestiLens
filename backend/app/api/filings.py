"""Filing detail and section endpoints (spec §24.2). Reads filings/document_chunks (Phase 1a/2a)."""

from __future__ import annotations

from collections import Counter
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.filings import service as diff_service
from app.filings.diff import DiffItem, word_diff
from app.filings.units import Unit
from app.models import Company, Filing
from app.repositories import filings as filing_repo
from app.schemas.filings import (
    DiffOp,
    DiffPassage,
    FilingDetail,
    FilingDiffCounts,
    FilingDiffItem,
    FilingDiffResponse,
    FilingSection,
    FilingSectionsResponse,
    FilingSummary,
)

router = APIRouter(prefix="/filings", tags=["Filings"])

_DB = Depends(get_db)


def _resolve(db: Session, filing_id: str) -> Filing:
    try:
        fid = int(filing_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "filing not found") from exc
    filing = filing_repo.get_filing(db, fid)
    if filing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "filing not found")
    return filing


@router.get("/{filing_id}", response_model=FilingDetail)
async def get_filing(filing_id: str, db: Session = _DB) -> FilingDetail:
    filing = _resolve(db, filing_id)
    company = db.get(Company, filing.company_id)
    return FilingDetail(
        filing_id=str(filing.id),
        filing_type=filing.filing_type,
        filing_date=filing.filing_date.isoformat() if filing.filing_date else None,
        period_end=filing.period_end.isoformat() if filing.period_end else None,
        accession_number=filing.accession_number,
        primary_document_url=filing.primary_document_url,
        company_ticker=company.ticker if company else "",
        items=filing.items,
        source_url=filing.source_url,
    )


@router.get("/{filing_id}/sections", response_model=FilingSectionsResponse)
async def get_filing_sections(filing_id: str, db: Session = _DB) -> FilingSectionsResponse:
    filing = _resolve(db, filing_id)
    chunks = filing_repo.get_filing_sections(db, document_id=filing.document_id)
    sections: list[FilingSection] = []
    seen: set[tuple[str, ...]] = set()
    for chunk in chunks:
        path = list(chunk.section_path or ([chunk.section] if chunk.section else []))
        key = tuple(path)
        if not path or key in seen:
            continue
        seen.add(key)
        sections.append(
            FilingSection(
                section_path=path,
                title=chunk.section or path[-1],
                char_start=chunk.char_start,
                char_end=chunk.char_end,
            )
        )
    return FilingSectionsResponse(filing_id=str(filing.id), sections=sections)


def to_summary(filing: Filing) -> FilingSummary:
    return FilingSummary(
        filing_id=str(filing.id),
        filing_type=filing.filing_type,
        filing_date=filing.filing_date.isoformat() if filing.filing_date else None,
        period_end=filing.period_end.isoformat() if filing.period_end else None,
        accession_number=filing.accession_number,
        primary_document_url=filing.primary_document_url,
    )


def _passage(unit: Unit | None, *, with_text: bool) -> DiffPassage | None:
    if unit is None:
        return None
    return DiffPassage(
        heading=unit.heading,
        source_ids=list(unit.source_ids),
        text=unit.text if with_text else None,
    )


def _to_item(item: DiffItem) -> FilingDiffItem:
    unit = item.new or item.old
    assert unit is not None  # noqa: S101 - a diff item always has at least one side
    reworded = item.status == "reworded" and item.old is not None and item.new is not None
    return FilingDiffItem(
        section=unit.section,
        kind=unit.kind,
        status=item.status,
        decided_by=item.decided_by,
        similarity=item.similarity,
        old=_passage(item.old, with_text=item.status == "removed"),
        new=_passage(item.new, with_text=item.status == "new"),
        word_diff=(
            [DiffOp(op=op, text=text) for op, text in word_diff(item.old.text, item.new.text)]
            if reworded and item.old and item.new
            else None
        ),
    )


@router.get("/{filing_id}/diff", response_model=FilingDiffResponse)
async def diff_filings(
    filing_id: str,
    against: str | None = None,
    kind: Literal["risk_factor", "section"] | None = None,
    db: Session = _DB,
) -> FilingDiffResponse:
    """What changed in this filing versus an older one of the same type (§37.4).

    `against` defaults to the previous filing of the same type — last year's 10-K, or last
    quarter's 10-Q ("what changed vs last quarter", §37.3). Deterministic: no LLM on this path.
    """
    filing = _resolve(db, filing_id)
    base = (
        _resolve(db, against) if against is not None else diff_service.previous_filing(db, filing)
    )
    if base is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no earlier parsed filing to compare with")
    if (base.company_id, base.filing_type) != (filing.company_id, filing.filing_type):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "filings must be the same type from the same company",
        )
    diff = diff_service.diff_filings(db, filing, base)
    items = [
        item
        for item in diff.items
        if kind is None or (item.new or item.old).kind == kind  # type: ignore[union-attr]
    ]
    # Never report "everything was removed" for a filing that simply has not been parsed yet.
    if not any(item.new for item in items) or not any(item.old for item in items):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "one of the filings has no parsed sections"
        )
    company = db.get(Company, filing.company_id)
    counts = Counter(item.status for item in items)
    return FilingDiffResponse(
        company_ticker=company.ticker if company else "",
        filing=to_summary(filing),
        against=to_summary(base),
        similarity_method=get_settings().diff_similarity,
        caption_detection=diff.caption_detection,
        counts=FilingDiffCounts.model_validate(dict(counts)),
        items=[_to_item(item) for item in items],
    )
