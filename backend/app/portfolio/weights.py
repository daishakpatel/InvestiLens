"""Holding-weight parsing and normalization (§37.2).

Weights are entered however the user likes (percent "30" or decimal "0.30"); we normalize them to
sum to exactly 1 so every downstream calculation (weighted metrics, HHI, portfolio volatility) has
a consistent basis. A duplicate ticker is merged by summing its weights.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.schemas.portfolio import Holding

_WEIGHT_PRECISION = Decimal("0.00000001")  # 8 dp, matching NUMERIC(28,8) elsewhere


@dataclass(frozen=True)
class NormalizedWeight:
    ticker: str
    weight: Decimal


def normalize(holdings: list[Holding]) -> list[NormalizedWeight]:
    """Merge duplicate tickers and scale weights to sum to 1. Raises on empty/non-positive input."""
    merged: dict[str, Decimal] = {}
    for h in holdings:
        if h.weight <= 0:
            raise ValueError(f"weight for {h.ticker} must be positive")
        key = h.ticker.upper()
        merged[key] = merged.get(key, Decimal(0)) + h.weight
    total = sum(merged.values(), Decimal(0))
    if total <= 0:
        raise ValueError("portfolio weights sum to zero")
    return [
        NormalizedWeight(ticker=t, weight=(w / total).quantize(_WEIGHT_PRECISION))
        for t, w in merged.items()
    ]
