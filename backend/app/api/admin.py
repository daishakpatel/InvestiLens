"""Admin (internal) endpoints (spec §24.2)."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.admin import EvalRunSummary, IngestionRunSummary, RefreshAccepted

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/ingestion-runs", response_model=list[IngestionRunSummary])
async def list_ingestion_runs() -> list[IngestionRunSummary]:
    return []


@router.get("/eval-runs", response_model=list[EvalRunSummary])
async def list_eval_runs() -> list[EvalRunSummary]:
    return []


@router.post("/companies/{ticker}/refresh", status_code=202, response_model=RefreshAccepted)
async def refresh_company(ticker: str) -> RefreshAccepted:
    return RefreshAccepted(ticker=ticker.upper(), job_id="job_refresh", status="queued")
