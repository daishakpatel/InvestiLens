"""Mock news source backed by frozen fixtures (Phase 1e). Offline (DR-004)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from app.providers.mocks._fixtures import load_json
from app.providers.news.base import NewsArticle, NewsSource

_TICKER_DIRS = {"NVDA": "nvda", "AAPL": "aapl", "JPM": "jpm"}


class MockNewsSource(NewsSource):
    def get_news(
        self, ticker: str, *, start: date | None = None, end: date | None = None
    ) -> Sequence[NewsArticle]:
        slug = _TICKER_DIRS.get(ticker.upper())
        if slug is None:
            return []
        payload = load_json(slug, "news.json")
        articles: list[NewsArticle] = []
        for row in payload["items"]:
            published = datetime.fromisoformat(row["published_at"].replace("Z", "+00:00"))
            if (start and published.date() < start) or (end and published.date() > end):
                continue
            articles.append(
                NewsArticle(
                    external_id=row["news_id"],
                    title=row["title"],
                    summary=row.get("description", ""),
                    url=row.get("url", ""),
                    publisher=row.get("publisher", ""),
                    published_at=published,
                    provider_category=row.get("category"),
                )
            )
        return articles
