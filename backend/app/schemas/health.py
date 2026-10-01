"""Health, readiness, and data-freshness meta schemas (spec §24.2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.common import Freshness


class Health(BaseModel):
    status: Literal["ok"] = "ok"


class Readiness(BaseModel):
    status: Literal["ready", "degraded"]
    checks: dict[str, bool]  # e.g. {"db": true, "redis": true, "queue": true}


class DataFreshnessResponse(BaseModel):
    ticker: str
    sources: list[Freshness]
