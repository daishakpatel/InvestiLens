"""News source factory: mock (fixtures) or live (Finnhub) per PROVIDER_MODE (DR-004)."""

from __future__ import annotations

from app.config import get_settings
from app.providers.news.base import NewsArticle, NewsSource


def get_news_source() -> NewsSource:
    if get_settings().provider_mode == "mock":
        from app.providers.news.mock import MockNewsSource

        return MockNewsSource()
    from app.providers.news.live import FinnhubNewsSource

    return FinnhubNewsSource()


__all__ = ["NewsArticle", "NewsSource", "get_news_source"]
