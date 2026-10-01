"""News data source abstraction (Phase 1e).

Separate from the API-facing `NewsProvider` (Phase 0c, returns `NewsItem`): ingestion needs the
raw article (headline, publisher, url, timestamp, provider summary) so it can categorize, score
relevance, deduplicate, and summarize. Only headline-level fields are ever stored (LGL-004,
ADR-0008) — never full article text.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class NewsArticle:
    """A raw news article from the provider (headline-level only, LGL-004)."""

    external_id: str
    title: str
    summary: str  # provider's short summary/description — NOT the full article body
    url: str
    publisher: str
    published_at: datetime
    provider_category: str | None = None  # provider's own tag, if any


class NewsSource(ABC):
    @abstractmethod
    def get_news(
        self, ticker: str, *, start: date | None = None, end: date | None = None
    ) -> Sequence[NewsArticle]:
        """Return recent company news (newest first)."""
