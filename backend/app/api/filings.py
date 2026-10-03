"""Filing detail and section endpoints (spec §24.2). Reads filings/document_chunks (Phase 1a/2a)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.errors import not_implemented
from app.db import get_db
from app.models import Company, Filing
from app.repositories import filings as filing_repo
from app.schemas.filings import FilingDetail, FilingSection, FilingSectionsResponse

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


@router.get("/{filing_id}/diff", response_model=None)
async def diff_filings(filing_id: str, against: str) -> None:
    """Filing-to-filing diff (Phase 6b). Not yet available."""
    raise not_implemented("Filing diff is a Phase 6 feature")
