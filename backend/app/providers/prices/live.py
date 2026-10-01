"""Live Tiingo price source (Phase 1d, ADR-0007).

Tiingo's daily endpoint returns raw and adjusted OHLCV plus per-day `divCash`/`splitFactor`, so a
single request yields both price history and corporate-action signals. The API token is sent as
an `Authorization` header (never in the URL/logs). Free tier: 50 req/hour — fine, since a full
backfill is one request per symbol (DR-002 reliability via HardenedHttpClient).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from app.config import get_settings
from app.providers.prices.base import PriceBar, PriceSource
from app.utils.http import HardenedHttpClient

ALLOWED_HOSTS = frozenset({"api.tiingo.com"})


def _dec(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


class TiingoPriceSource(PriceSource):
    def __init__(self, client: HardenedHttpClient | None = None) -> None:
        settings = get_settings()
        if client is None and not settings.tiingo_api_key:
            raise RuntimeError("TIINGO_API_KEY is required for live price ingestion (ADR-0007)")
        self._http = client or HardenedHttpClient(
            user_agent=settings.sec_user_agent,
            allowed_hosts=ALLOWED_HOSTS,
            rate_per_sec=settings.price_rate_limit_per_sec,
            default_headers={
                "Authorization": f"Token {settings.tiingo_api_key}",
                "Content-Type": "application/json",
            },
        )

    def get_prices(
        self, ticker: str, *, start: date | None = None, end: date | None = None
    ) -> Sequence[PriceBar]:
        params = ["format=json", "resampleFreq=daily"]
        if start:
            params.append(f"startDate={start.isoformat()}")
        if end:
            params.append(f"endDate={end.isoformat()}")
        url = f"https://api.tiingo.com/tiingo/daily/{ticker.lower()}/prices?{'&'.join(params)}"
        rows = json.loads(self._http.get_bytes(url))
        return [self._to_bar(row) for row in rows]

    @staticmethod
    def _to_bar(row: dict[str, Any]) -> PriceBar:
        return PriceBar(
            date=date.fromisoformat(row["date"][:10]),
            open=_dec(row.get("open")),
            high=_dec(row.get("high")),
            low=_dec(row.get("low")),
            close=_dec(row.get("close")),
            adj_close=_dec(row.get("adjClose")),
            volume=int(row["volume"]) if row.get("volume") is not None else None,
            div_cash=_dec(row.get("divCash")) or Decimal(0),
            split_factor=_dec(row.get("splitFactor")) or Decimal(1),
        )
