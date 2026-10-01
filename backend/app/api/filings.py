"""Filing detail and section endpoints (spec §24.2)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.errors import not_implemented
from app.schemas.filings import FilingDetail, FilingSection, FilingSectionsResponse

router = APIRouter(prefix="/filings", tags=["Filings"])


@router.get("/{filing_id}", response_model=FilingDetail)
async def get_filing(filing_id: str) -> FilingDetail:
    return FilingDetail(
        filing_id=filing_id,
        filing_type="10-K",
        filing_date="2025-02-26",
        period_end="2025-01-26",
        accession_number="0001045810-25-000023",
        company_ticker="NVDA",
    )


@router.get("/{filing_id}/sections", response_model=FilingSectionsResponse)
async def get_filing_sections(filing_id: str) -> FilingSectionsResponse:
    return FilingSectionsResponse(
        filing_id=filing_id,
        sections=[FilingSection(section_path=["Item 7", "MD&A"], title="Management's Discussion")],
    )


@router.get("/{filing_id}/diff", response_model=None)
async def diff_filings(filing_id: str, against: str) -> None:
    """Filing-to-filing diff (P2)."""
    raise not_implemented("Filing diff is a Phase 6 feature")
