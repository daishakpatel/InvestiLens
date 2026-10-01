"""Price data source abstraction (Phase 1d).

Separate from the API-facing `PriceProvider` (Phase 0c, returns `PricePoint`): ingestion needs
the richer bar — both raw and split/dividend-adjusted close (DR-025), plus the per-day dividend
cash and split factor Tiingo embeds, from which corporate actions are derived. A live (Tiingo)
and a mock (frozen fixtures) implementation are switched by `PROVIDER_MODE`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class PriceBar:
    """One daily OHLCV bar with adjusted close and corporate-action signals (DR-025)."""

    date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None  # RAW close — use for P/E and market cap (contemporaneous shares)
    adj_close: Decimal | None  # split/dividend-adjusted — use for return charts
    volume: int | None
    div_cash: Decimal = Decimal(0)  # per-share dividend with ex-date == this bar's date
    split_factor: Decimal = Decimal(1)  # >1 on a split ex-date (e.g. 10 for a 10:1 split)


class PriceSource(ABC):
    @abstractmethod
    def get_prices(
        self, ticker: str, *, start: date | None = None, end: date | None = None
    ) -> Sequence[PriceBar]:
        """Return daily bars (oldest first) for the requested range."""
