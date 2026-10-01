"""SEC source factory: mock (fixtures) or live (EDGAR) per PROVIDER_MODE (DR-004)."""

from __future__ import annotations

from app.config import get_settings
from app.providers.sec.base import CompanyRef, FilingRef, SecSource


def get_sec_source() -> SecSource:
    if get_settings().provider_mode == "mock":
        from app.providers.sec.mock import MockSecSource

        return MockSecSource()
    from app.providers.sec.live import LiveSecSource

    return LiveSecSource()


__all__ = ["CompanyRef", "FilingRef", "SecSource", "get_sec_source"]
