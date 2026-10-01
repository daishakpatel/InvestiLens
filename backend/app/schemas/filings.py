"""Filing list, detail, and section schemas (spec §24.2)."""

from __future__ import annotations

from pydantic import BaseModel


class FilingSummary(BaseModel):
    filing_id: str
    filing_type: str
    filing_date: str | None = None
    period_end: str | None = None
    accession_number: str
    primary_document_url: str | None = None


class FilingDetail(FilingSummary):
    company_ticker: str
    items: list[str] | None = None
    source_url: str | None = None


class FilingSection(BaseModel):
    section_path: list[str]
    title: str
    char_start: int | None = None
    char_end: int | None = None


class FilingSectionsResponse(BaseModel):
    filing_id: str
    sections: list[FilingSection]
