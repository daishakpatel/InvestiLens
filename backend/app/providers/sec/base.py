"""SEC data source abstraction used by the ingestion pipeline (Phase 1a).

This is deliberately separate from the API-facing `FilingsProvider` (Phase 0c): ingestion needs
raw submissions, XBRL companyfacts, and raw document bytes, whereas the API returns typed
response models. Both a live (EDGAR) and a mock (frozen fixtures) implementation exist, switched
by `PROVIDER_MODE`.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

# FR-EX-005: press-release exhibits only (EX-99, EX-99.1, EX-99.2, …); EX-10.x and the rest are
# not fetched for now.
_PRESS_RELEASE = re.compile(r"^EX-99(\.\d+)?$", re.I)


def is_press_release_exhibit(exhibit_type: str) -> bool:
    return bool(_PRESS_RELEASE.match(exhibit_type.strip()))


@dataclass(frozen=True)
class CompanyRef:
    """A company from EDGAR's `company_tickers.json`."""

    cik: str  # zero-padded 10-digit
    ticker: str
    title: str


@dataclass(frozen=True)
class CompanyMetadata:
    """Company profile fields from EDGAR `submissions` (top-level), separate from the filing list.

    Enables peer-set grouping by SIC/industry (§37.1) and calendarization by fiscal-year end.
    `fiscal_year_end` is normalized to "MM-DD" (EDGAR reports it as "MMDD").
    """

    name: str | None = None
    sic_code: str | None = None
    industry: str | None = None  # EDGAR `sicDescription`
    exchange: str | None = None
    fiscal_year_end: str | None = None  # "MM-DD"


@dataclass(frozen=True)
class FilingRef:
    """One filing, normalized from the `submissions` API (or a fixture manifest)."""

    cik: str
    form: str
    accession_number: str
    primary_document: str
    filing_date: str  # ISO-8601
    report_date: str | None
    primary_doc_url: str
    items: tuple[str, ...] | None = None  # 8-K item codes if provided by the source
    local_file: str | None = None  # mock only: fixture filename
    accepted_at: str | None = None  # EDGAR acceptance time, ISO-8601 UTC


@dataclass(frozen=True)
class ExhibitRef:
    """One exhibit of a filing, from the filing index (FR-EX-005)."""

    filing_accession: str
    exhibit_type: str  # "EX-99.1"
    filename: str
    url: str
    size_bytes: int | None = None
    local_file: str | None = None  # mock only: fixture filename


class SecSource(ABC):
    @abstractmethod
    def company_tickers(self) -> Sequence[CompanyRef]:
        """Return the ticker↔CIK reference list."""

    @abstractmethod
    def list_filings(self, cik: str, *, since: date | None = None) -> Sequence[FilingRef]:
        """Return the company's filings, newest first.

        Without `since`, only what the source lists first (EDGAR's recent block, about 1,000
        filings). With it, older pages are read too until they cover `since` (FR-EX-011).
        """

    @abstractmethod
    def company_metadata(self, cik: str) -> CompanyMetadata:
        """Return company profile metadata (SIC, industry, exchange, fiscal-year end)."""

    @abstractmethod
    def companyfacts(self, cik: str) -> dict[str, Any]:
        """Return the raw XBRL `companyfacts` JSON."""

    @abstractmethod
    def fetch_document(self, ref: FilingRef) -> bytes:
        """Return the raw bytes of a filing's primary document."""

    @abstractmethod
    def list_exhibits(self, filing: FilingRef) -> Sequence[ExhibitRef]:
        """Return the filing's press-release exhibits (EX-99.x), in filing order."""

    @abstractmethod
    def fetch_exhibit(self, exhibit: ExhibitRef) -> bytes:
        """Return the raw bytes of one exhibit."""
