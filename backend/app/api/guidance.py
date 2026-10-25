"""Guidance vs actual endpoints (Phase 7i, FR-GD-014, ADR-0047).

Read-only over stored guidance and outcomes: extraction runs after parsing or by
`make guidance-backfill`, never on page load. Company guidance only; no consensus estimates.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.companies import _resolve
from app.db import get_db
from app.guidance import service
from app.schemas.guidance import GuidanceResponse, GuidanceTrackRecord

router = APIRouter(tags=["Guidance"])

_DB = Depends(get_db, scope="function")


@router.get("/companies/{ticker}/guidance", response_model=GuidanceResponse)
def company_guidance(
    ticker: str,
    fiscal_year: int | None = Query(default=None, ge=1990, le=2100),
    db: Session = _DB,
) -> GuidanceResponse:
    """Verified guidance with outcome and revisions, newest period first (FR-GD-014)."""
    return service.guidance(db, _resolve(db, ticker), fiscal_year=fiscal_year)


@router.get("/companies/{ticker}/guidance/track-record", response_model=GuidanceTrackRecord)
def company_guidance_track_record(ticker: str, db: Session = _DB) -> GuidanceTrackRecord:
    """Revenue against the initial guided range over the last 8 guided quarters (FR-GD-011)."""
    return service.track_record(db, _resolve(db, ticker))
