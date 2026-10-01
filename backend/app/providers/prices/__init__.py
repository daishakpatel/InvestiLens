"""Price source factory: mock (fixtures) or live (Tiingo) per PROVIDER_MODE (DR-004)."""

from __future__ import annotations

from app.config import get_settings
from app.providers.prices.base import PriceBar, PriceSource


def get_price_source() -> PriceSource:
    if get_settings().provider_mode == "mock":
        from app.providers.prices.mock import MockPriceSource

        return MockPriceSource()
    from app.providers.prices.live import TiingoPriceSource

    return TiingoPriceSource()


__all__ = ["PriceBar", "PriceSource", "get_price_source"]
