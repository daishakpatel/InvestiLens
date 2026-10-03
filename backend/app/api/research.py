"""Research job endpoints: async generation, polling, SSE progress, report retrieval.

Follows the async job pattern (spec §25.1): POST enqueues and returns 202 + ids; progress via
polling or SSE. `Idempotency-Key` single-flights duplicate requests (API-003, JOB-005). Actual
generation runs on the Phase 5d worker (ADR-0017); until then an enqueued job stays `queued`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.api.errors import not_implemented
from app.config import get_settings
from app.db import get_db
from app.models import Company, Job
from app.repositories import companies as company_repo
from app.repositories import jobs as job_repo
from app.repositories import reports as report_repo
from app.research.prompts import REPORT_PROMPT_VERSION
from app.schemas.jobs import (
    JobState,
    JobStatus,
    ResearchAccepted,
    ResearchReportEnvelope,
    ResearchRequest,
)
from app.schemas.research import ResearchReport

router = APIRouter(prefix="/research", tags=["Research"])

_DB = Depends(get_db)
_USER = Depends(get_current_user_id)
_JOB_TYPE = "research_report"

# jobs.status (queued|running|done|failed) → the API's JobStatus vocabulary.
_STATUS_MAP: dict[str, JobStatus] = {
    "queued": "queued",
    "running": "processing",
    "done": "done",
    "failed": "failed",
}


def _empty_report() -> ResearchReport:
    """A valid, all-empty report for a job that has not generated yet (honest `queued` state)."""
    return ResearchReport(
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


def _accepted(job: Job) -> ResearchAccepted:
    return ResearchAccepted(
        research_id=str(job.result_ref) if job.result_ref else "",
        job_id=str(job.id),
        status=_STATUS_MAP.get(job.status, "processing"),
    )


@router.post("", status_code=202, response_model=ResearchAccepted)
async def create_research(
    body: ResearchRequest,
    db: Session = _DB,
    user_id: int = _USER,  # anonymous users may not generate reports (ADR-0006)
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ResearchAccepted:
    company = company_repo.get_by_ticker(db, body.ticker)
    if company is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"company {body.ticker.upper()} not ingested"
        )

    # Single-flight: an idempotency-key match, else any in-flight job for the same company.
    if idempotency_key:
        existing = job_repo.find_by_idempotency_key(db, job_type=_JOB_TYPE, key=idempotency_key)
        if existing is not None:
            return _accepted(existing)
    active = job_repo.find_active_for_company(db, job_type=_JOB_TYPE, ticker=company.ticker)
    if active is not None:
        return _accepted(active)

    settings = get_settings()
    report = report_repo.create_report(
        db,
        company_id=company.id,
        user_id=user_id,  # saved-report association (§26.2, scope item 11)
        model=settings.llm_model_strong,
        prompt_version=REPORT_PROMPT_VERSION,
        data_version="pending",
        status="pending",
    )
    job = job_repo.create_job(
        db,
        job_type=_JOB_TYPE,
        params={
            "ticker": company.ticker,
            "idempotency_key": idempotency_key,
            "force_refresh": body.force_refresh,
        },
        created_by=user_id,
        result_ref=str(report.id),
    )
    db.commit()
    return _accepted(job)


@router.get("/jobs/{job_id}", response_model=JobState)
async def get_job(job_id: int, db: Session = _DB) -> JobState:
    job = job_repo.get_job(db, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    return JobState(
        status=_STATUS_MAP.get(job.status, "processing"),
        progress=job.progress or 0,
        stage=job.status,
        stages=[],
    )


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: int, db: Session = _DB) -> StreamingResponse:
    """SSE stream of job progress (API-004). Emits the current state, then closes."""
    job = job_repo.get_job(db, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    status_str = _STATUS_MAP.get(job.status, "processing")
    progress = job.progress or 0

    async def _stream() -> AsyncIterator[bytes]:
        frame = f'event: progress\ndata: {{"progress": {progress}, "stage": "{status_str}"}}\n\n'
        yield frame.encode()

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.get("/{research_id}", response_model=ResearchReportEnvelope)
async def get_research(research_id: int, db: Session = _DB) -> ResearchReportEnvelope:
    report = report_repo.get_report(db, research_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
    company = db.get(Company, report.company_id)
    payload = report.report_json
    return ResearchReportEnvelope(
        research_id=str(report.id),
        ticker=company.ticker if company else "",
        generated_at=report.generated_at.isoformat() if report.generated_at else None,
        model=report.model,
        prompt_version=report.prompt_version,
        data_version=report.data_version,
        report=ResearchReport.model_validate(payload) if payload else _empty_report(),
    )


@router.get("/{research_id}/diff", response_model=None)
async def diff_research(research_id: str, against: str) -> None:
    raise not_implemented("Research diff is a Phase 6 feature")


@router.get("/{research_id}/export", response_model=None)
async def export_research(research_id: str, format: str = "pdf") -> None:
    raise not_implemented("Report export lands in Phase 4d")
