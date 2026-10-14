"""Price source factory: mock (fixtures) or live (Tiingo), per PRICE_PROVIDER or PROVIDER_MODE."""

from __future__ import annotations

from app.config import get_settings
from app.providers.prices.base import PriceBar, PriceSource


def get_price_source() -> PriceSource:
    settings = get_settings()
    # PRICE_PROVIDER picks the price source on its own, like LLM_PROVIDER (ADR-0035).
    provider = settings.price_provider or ("mock" if settings.provider_mode == "mock" else "tiingo")
    if provider == "mock":
        from app.providers.prices.mock import MockPriceSource

        return MockPriceSource()
    from app.providers.prices.live import TiingoPriceSource

    return TiingoPriceSource()


__all__ = ["PriceBar", "PriceSource", "get_price_source"]
