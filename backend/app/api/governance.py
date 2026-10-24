"""Governance endpoints (Phase 7g, FR-GV-011, ADR-0045).

Read-only over proxy statements: Tier A (Pay Versus Performance XBRL), Tier B (validated
Summary Compensation Table rows and pay ratio) and cached Tier C (quoted board facts). These
handlers never call a model; an unextracted proxy reads `pending`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.companies import _resolve
from app.db import get_db
from app.governance import service
from app.schemas.governance import GovernanceHistoryResponse, GovernanceResponse

router = APIRouter(tags=["Governance"])

_DB = Depends(get_db, scope="function")
_YEAR = Query(default=None, ge=1990, le=2100, description="Proxy fiscal year; default the latest")


@router.get("/companies/{ticker}/governance", response_model=GovernanceResponse)
def governance(
    ticker: str, fiscal_year: int | None = _YEAR, db: Session = _DB
) -> GovernanceResponse:
    response = service.governance(db, _resolve(db, ticker), fiscal_year)
    if response is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no proxy for fiscal year {fiscal_year}")
    return response


@router.get("/companies/{ticker}/governance/history", response_model=GovernanceHistoryResponse)
def governance_history(ticker: str, db: Session = _DB) -> GovernanceHistoryResponse:
    return service.history(db, _resolve(db, ticker))
