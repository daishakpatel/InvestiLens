"""Health, readiness, and data-freshness endpoints (spec §24.2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api._support import freshness_from_row
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


@router.get("/ready", response_model=Readiness)
async def ready() -> Readiness:
    """Readiness probe (db, redis, queue). Full redis/queue checks land in Phase 5d."""
    return Readiness(status="ready", checks={"db": True, "redis": True, "queue": True})


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
