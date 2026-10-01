"""Mock PriceProvider backed by frozen (synthetic) price CSVs (Phase 0d, DR-004)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from app.providers.base import PriceProvider
from app.providers.mocks._fixtures import company_reference, load_csv_rows
from app.schemas.company import PricePoint

_TICKER_DIRS = {"NVDA": "nvda", "AAPL": "aapl", "JPM": "jpm"}


def _dec(value: str) -> Decimal | None:
    return Decimal(value) if value else None


class MockPriceProvider(PriceProvider):
    async def get_prices(
        self, ticker: str, start: date | None = None, end: date | None = None
    ) -> Sequence[PricePoint]:
        key = ticker.upper()
        if key not in _TICKER_DIRS or key not in company_reference():
            return []
        points = []
        for row in load_csv_rows(_TICKER_DIRS[key], "prices.csv"):
            day = date.fromisoformat(row["date"])
            if (start and day < start) or (end and day > end):
                continue
            points.append(
                PricePoint(
                    date=row["date"],
                    open=_dec(row["open"]),
                    high=_dec(row["high"]),
                    low=_dec(row["low"]),
                    close=_dec(row["close"]),
                    adj_close=_dec(row["adj_close"]),
                    volume=int(row["volume"]),
                )
            )
        return points
