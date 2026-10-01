"""Provider interfaces (spec §7, §33.1 contract pack).

These abstract base classes are the seam between the app and every external system. Concrete
implementations (real + mock) arrive in later phases (Phase 0d mocks, Phase 1/2/3 real). Every
implementation MUST apply timeouts, retries with backoff, structured logging, and response
caching (DR-002), and validate responses against Pydantic schemas before use (DR-003).

Method signatures use primitive/typed inputs and return already-validated schema objects, so
callers never touch raw provider payloads.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import date
from typing import Any

from app.schemas.company import (
    Company,
    InsiderTransaction,
    OwnershipHolding,
    PricePoint,
)
from app.schemas.filings import FilingDetail, FilingSummary
from app.schemas.news import NewsItem


class FilingsProvider(ABC):
    """SEC EDGAR filings, XBRL facts, and company reference data."""

    @abstractmethod
    async def resolve_company(self, ticker_or_cik: str) -> Company | None:
        """Map a ticker or CIK to a company, or None if unknown."""

    @abstractmethod
    async def list_filings(
        self, cik: str, filing_type: str | None = None, limit: int = 50
    ) -> Sequence[FilingSummary]:
        """Return recent filings for a company, newest first."""

    @abstractmethod
    async def get_filing(self, accession_number: str) -> FilingDetail | None:
        """Return one filing's metadata by accession number."""


class PriceProvider(ABC):
    """Daily price history and corporate actions (ADR-0007)."""

    @abstractmethod
    async def get_prices(
        self, ticker: str, start: date | None = None, end: date | None = None
    ) -> Sequence[PricePoint]:
        """Return daily OHLCV bars in the requested range."""


class NewsProvider(ABC):
    """Company news (ADR-0008). Only headline-level fields are stored (LGL-004)."""

    @abstractmethod
    async def get_news(
        self, ticker: str, start: date | None = None, end: date | None = None
    ) -> Sequence[NewsItem]:
        """Return recent news items for a company."""


class OwnershipProvider(ABC):
    """Form 4 insider transactions and 13F holdings (P2)."""

    @abstractmethod
    async def get_insiders(self, ticker: str) -> Sequence[InsiderTransaction]: ...

    @abstractmethod
    async def get_ownership(self, ticker: str) -> Sequence[OwnershipHolding]: ...


class LLMMessage:
    """A minimal chat message (role + content) passed to an LLM."""

    __slots__ = ("content", "role")

    def __init__(self, role: str, content: str) -> None:
        self.role = role
        self.content = content


class LLMClient(ABC):
    """Text/structured generation behind a provider-agnostic interface (ADR-0009).

    Implementations MUST log every call to `llm_calls` (NFR-015) and treat all message content
    from filings/news as untrusted data, never instructions (P8).
    """

    @abstractmethod
    async def complete(self, messages: Sequence[LLMMessage], *, model: str, max_tokens: int) -> str:
        """Return a plain-text completion."""

    @abstractmethod
    async def complete_json(
        self,
        messages: Sequence[LLMMessage],
        *,
        model: str,
        schema: dict[str, Any],
        max_tokens: int,
    ) -> dict[str, Any]:
        """Return a JSON object validated against `schema` (structured output)."""


class EmbeddingClient(ABC):
    """Text embeddings behind a provider-agnostic interface (ADR-0010)."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding vector dimension (must match the DB `vector(N)` column)."""

    @abstractmethod
    async def embed(
        self, texts: Sequence[str], *, input_type: str = "document"
    ) -> Sequence[Sequence[float]]:
        """Return one embedding vector per input text."""
