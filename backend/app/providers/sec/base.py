"""SEC data source abstraction used by the ingestion pipeline (Phase 1a).

This is deliberately separate from the API-facing `FilingsProvider` (Phase 0c): ingestion needs
raw submissions, XBRL companyfacts, and raw document bytes, whereas the API returns typed
response models. Both a live (EDGAR) and a mock (frozen fixtures) implementation exist, switched
by `PROVIDER_MODE`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CompanyRef:
    """A company from EDGAR's `company_tickers.json`."""

    cik: str  # zero-padded 10-digit
    ticker: str
    title: str


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


class SecSource(ABC):
    @abstractmethod
    def company_tickers(self) -> Sequence[CompanyRef]:
        """Return the ticker↔CIK reference list."""

    @abstractmethod
    def list_filings(self, cik: str) -> Sequence[FilingRef]:
        """Return all discoverable filings for a company (newest first)."""

    @abstractmethod
    def companyfacts(self, cik: str) -> dict[str, Any]:
        """Return the raw XBRL `companyfacts` JSON."""

    @abstractmethod
    def fetch_document(self, ref: FilingRef) -> bytes:
        """Return the raw bytes of a filing's primary document."""
