"""Health, readiness, and data-freshness endpoints (spec §24.2)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api._support import freshness_from_row
from app.config import get_settings
from app.db import get_db
from app.repositories import companies as company_repo
from app.repositories import freshness as freshness_repo
from app.schemas.health import DataFreshnessResponse, Health, Readiness

router = APIRouter(tags=["Health"])

_DB = Depends(get_db)


@router.get("/health", response_model=Health)
async def health() -> Health:
    """Liveness probe."""
    return Health()


def _db_ok(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:  # a dead DB connection must never crash the readiness probe itself
        return False


def _redis_ok() -> bool:
    """Only meaningful once something actually depends on Redis (rate_limit_backend="redis",
    ADR-0022); otherwise it's not a readiness dependency and we don't manufacture a false one."""
    settings = get_settings()
    if settings.rate_limit_backend != "redis":
        return True
    try:
        import redis

        redis.from_url(settings.redis_url).ping()
        return True
    except Exception:
        return False


@router.get("/ready", response_model=Readiness)
async def ready(db: Session = _DB) -> Readiness:
    """Readiness probe: DB and (when in use) Redis are checked for real; `queue` stays a static
    `True` until the Phase 5d worker exists to report its own health."""
    checks = {"db": _db_ok(db), "redis": _redis_ok(), "queue": True}
    readiness_status: Literal["ready", "degraded"] = "ready" if all(checks.values()) else "degraded"
    return Readiness(status=readiness_status, checks=checks)


@router.get("/meta/data-freshness/{ticker}", response_model=DataFreshnessResponse, tags=["Meta"])
async def data_freshness(ticker: str, db: Session = _DB) -> DataFreshnessResponse:
    company = company_repo.get_by_ticker(db, ticker)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"company {ticker.upper()} not ingested")
    rows = freshness_repo.list_for_company(db, company_id=company.id)
    return DataFreshnessResponse(
        ticker=company.ticker,
        sources=[freshness_from_row(r, source=r.source) for r in rows],
    )
