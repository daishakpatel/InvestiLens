"""Mock price source backed by frozen CSV fixtures (Phase 1d). Fully offline (DR-004)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from app.providers.mocks._fixtures import load_csv_rows
from app.providers.prices.base import PriceBar, PriceSource

_TICKER_DIRS = {"NVDA": "nvda", "AAPL": "aapl", "JPM": "jpm"}


def _dec(value: str | None) -> Decimal | None:
    return Decimal(value) if value else None


class MockPriceSource(PriceSource):
    def get_prices(
        self, ticker: str, *, start: date | None = None, end: date | None = None
    ) -> Sequence[PriceBar]:
        slug = _TICKER_DIRS.get(ticker.upper())
        if slug is None:
            return []
        bars: list[PriceBar] = []
        for row in load_csv_rows(slug, "prices.csv"):
            day = date.fromisoformat(row["date"])
            if (start and day < start) or (end and day > end):
                continue
            bars.append(
                PriceBar(
                    date=day,
                    open=_dec(row.get("open")),
                    high=_dec(row.get("high")),
                    low=_dec(row.get("low")),
                    close=_dec(row.get("close")),
                    adj_close=_dec(row.get("adj_close")),
                    volume=int(row["volume"]) if row.get("volume") else None,
                    div_cash=_dec(row.get("div_cash")) or Decimal(0),
                    split_factor=_dec(row.get("split_factor")) or Decimal(1),
                )
            )
        return bars
