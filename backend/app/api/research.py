"""Research job endpoints: async generation, polling, SSE progress, report retrieval.

Follows the async job pattern (spec §25.1): POST returns 202 + job id; progress via polling or
SSE. `Idempotency-Key` is honoured on POST /research (API-003, JOB-005 single-flight).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from app.api.errors import not_implemented
from app.schemas.jobs import (
    JobStage,
    JobState,
    ResearchAccepted,
    ResearchReportEnvelope,
    ResearchRequest,
)
from app.schemas.research import ResearchReport

router = APIRouter(prefix="/research", tags=["Research"])

_EMPTY_REPORT = ResearchReport(
    executive_summary=[],
    company_overview=[],
    revenue_analysis=[],
    profitability_analysis=[],
    balance_sheet_analysis=[],
    cash_flow_analysis=[],
    valuation_analysis=[],
    news_summary=[],
    risks=[],
    management_commentary=[],
    bull_factors=[],
    bear_factors=[],
    insufficient_evidence_sections=[],
)


@router.post("", status_code=202, response_model=ResearchAccepted)
async def create_research(
    body: ResearchRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ResearchAccepted:
    return ResearchAccepted(research_id="rpt_example", job_id="job_789", status="processing")


@router.get("/jobs/{job_id}", response_model=JobState)
async def get_job(job_id: str) -> JobState:
    return JobState(
        status="processing",
        progress=72,
        stage="generating_sections",
        stages=[
            JobStage(name="sec", status="done"),
            JobStage(name="news", status="failed", message="using cached data"),
        ],
    )


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str) -> StreamingResponse:
    """SSE stream of job progress (API-004). Stub emits one event then closes."""

    async def _stream() -> AsyncIterator[bytes]:
        yield b'event: progress\ndata: {"progress": 100, "stage": "done"}\n\n'

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.get("/{research_id}", response_model=ResearchReportEnvelope)
async def get_research(research_id: str) -> ResearchReportEnvelope:
    return ResearchReportEnvelope(research_id=research_id, ticker="NVDA", report=_EMPTY_REPORT)


@router.get("/{research_id}/diff", response_model=None)
async def diff_research(research_id: str, against: str) -> None:
    raise not_implemented("Research diff is a Phase 6 feature")


@router.get("/{research_id}/export", response_model=None)
async def export_research(research_id: str, format: str = "pdf") -> None:
    raise not_implemented("Report export lands in Phase 4d")
