"""News source factory: mock (fixtures) or live (Finnhub), per NEWS_PROVIDER or PROVIDER_MODE."""

from __future__ import annotations

from app.config import get_settings
from app.providers.news.base import NewsArticle, NewsSource


def get_news_source() -> NewsSource:
    settings = get_settings()
    # NEWS_PROVIDER picks the news source on its own, like PRICE_PROVIDER (ADR-0038).
    provider = settings.news_provider or ("mock" if settings.provider_mode == "mock" else "finnhub")
    if provider == "mock":
        from app.providers.news.mock import MockNewsSource

        return MockNewsSource()
    from app.providers.news.live import FinnhubNewsSource

    return FinnhubNewsSource()


__all__ = ["NewsArticle", "NewsSource", "get_news_source"]
