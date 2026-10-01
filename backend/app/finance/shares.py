"""Share-count helpers for market cap (DR-025 multi-class handling).

Shares outstanding come from the filing cover page (`dei:EntityCommonStockSharesOutstanding`),
not from price data. Multi-class companies (e.g. Alphabet A/B/C) report one fact per class;
market cap sums the classes.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal


def total_shares_outstanding(class_counts: Sequence[Decimal | None]) -> Decimal | None:
    """Sum share counts across classes. Returns None only if no class has a value."""
    present = [c for c in class_counts if c is not None]
    return sum(present, Decimal(0)) if present else None
