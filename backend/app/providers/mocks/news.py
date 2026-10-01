"""Mock NewsProvider backed by frozen (synthetic) news JSON (Phase 0d, DR-004)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from app.providers.base import NewsProvider
from app.providers.mocks._fixtures import load_json
from app.schemas.news import NewsItem

_TICKER_DIRS = {"NVDA": "nvda", "AAPL": "aapl", "JPM": "jpm"}


class MockNewsProvider(NewsProvider):
    async def get_news(
        self, ticker: str, start: date | None = None, end: date | None = None
    ) -> Sequence[NewsItem]:
        key = ticker.upper()
        if key not in _TICKER_DIRS:
            return []
        payload = load_json(_TICKER_DIRS[key], "news.json")
        items = []
        for row in payload["items"]:
            published = datetime.fromisoformat(row["published_at"].replace("Z", "+00:00"))
            if (start and published.date() < start) or (end and published.date() > end):
                continue
            items.append(NewsItem(**row))
        return items
