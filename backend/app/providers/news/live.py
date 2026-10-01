"""Live Finnhub news source (Phase 1e, ADR-0008).

Finnhub `company-news` returns headline, source, url, unix datetime, and a short summary — no
full article body, matching the license (LGL-004). The API token is sent as the `X-Finnhub-Token`
header (never in the URL/logs). Free tier: 60 calls/min, 1y history, North-American companies.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any

from app.config import get_settings
from app.providers.news.base import NewsArticle, NewsSource
from app.utils.http import HardenedHttpClient

ALLOWED_HOSTS = frozenset({"finnhub.io"})


class FinnhubNewsSource(NewsSource):
    def __init__(self, client: HardenedHttpClient | None = None) -> None:
        settings = get_settings()
        if client is None and not settings.finnhub_api_key:
            raise RuntimeError("FINNHUB_API_KEY is required for live news ingestion (ADR-0008)")
        self._http = client or HardenedHttpClient(
            user_agent=settings.sec_user_agent,
            allowed_hosts=ALLOWED_HOSTS,
            rate_per_sec=settings.news_rate_limit_per_sec,
            default_headers={"X-Finnhub-Token": settings.finnhub_api_key},
        )

    def get_news(
        self, ticker: str, *, start: date | None = None, end: date | None = None
    ) -> Sequence[NewsArticle]:
        end = end or datetime.now(UTC).date()
        start = start or end
        url = (
            f"https://finnhub.io/api/v1/company-news?symbol={ticker.upper()}"
            f"&from={start.isoformat()}&to={end.isoformat()}"
        )
        rows = json.loads(self._http.get_bytes(url))
        return [self._to_article(row) for row in rows if row.get("headline")]

    @staticmethod
    def _to_article(row: dict[str, Any]) -> NewsArticle:
        return NewsArticle(
            external_id=str(row.get("id", "")),
            title=row["headline"],
            summary=row.get("summary", ""),
            url=row.get("url", ""),
            publisher=row.get("source", ""),
            published_at=datetime.fromtimestamp(row.get("datetime", 0), tz=UTC),
            provider_category=row.get("category"),
        )
