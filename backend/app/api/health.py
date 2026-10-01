"""Health, readiness, and data-freshness endpoints (spec §24.2)."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.common import Freshness
from app.schemas.health import DataFreshnessResponse, Health, Readiness

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=Health)
async def health() -> Health:
    """Liveness probe."""
    return Health()


@router.get("/ready", response_model=Readiness)
async def ready() -> Readiness:
    """Readiness probe (db, redis, queue). Real checks land in Phase 4a/5d."""
    return Readiness(status="ready", checks={"db": True, "redis": True, "queue": True})


@router.get("/meta/data-freshness/{ticker}", response_model=DataFreshnessResponse, tags=["Meta"])
async def data_freshness(ticker: str) -> DataFreshnessResponse:
    return DataFreshnessResponse(
        ticker=ticker.upper(),
        sources=[Freshness(as_of="2026-09-29T00:00:00Z", source="sec", freshness_status="fresh")],
    )
