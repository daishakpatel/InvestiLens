"""News item response schema (spec §10.8, §24.2).

Headline-level only by default; full text is stored/returned only where licensed (LGL-004).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import Freshness


class NewsItem(BaseModel):
    news_id: str
    title: str
    description: str | None = None
    url: str | None = None
    publisher: str | None = None
    published_at: str | None = None  # ISO-8601 UTC
    category: str | None = None
    relevance_score: float | None = Field(default=None, ge=0, le=1)


class NewsResponse(BaseModel):
    ticker: str
    items: list[NewsItem]
    next_cursor: str | None = None
    freshness: Freshness
