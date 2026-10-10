"""Portfolio-analysis endpoint (§37.2).

A POST (it carries a body of holdings) but a pure deterministic read: weighted metrics,
concentration, price-based risk, and aggregated *already-cited* risk themes from existing reports.
No LLM generation happens here, so it needs no auth or AI budget. The response also carries the
per-holding data the client uses to recompute aggregates on a what-if weight change (§37.2 item 10)
without another round-trip. Output is analysis only — never a recommendation (LGL-006).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.portfolio.analysis import analyze
from app.schemas.portfolio import PortfolioAnalysis, PortfolioRequest

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])

_DB = Depends(get_db)


@router.post("/analyze", response_model=PortfolioAnalysis)
def analyze_portfolio(body: PortfolioRequest, db: Session = _DB) -> PortfolioAnalysis:
    """Analyze a hypothetical portfolio of user-entered ticker + weight holdings."""
    try:
        return analyze(db, body)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
