"""Interactive-queue tasks (JOB-003): user-triggered report generation.

This is what `POST /research` was waiting on — Phase 4a created the `jobs`/`research_reports`
rows and single-flighted duplicates, but the worker that actually runs generation was deferred to
here (ADR-0017). The task adopts the pre-created `jobs` row so the API's single-flight stays
authoritative and the client polls the same row through to `done`.
"""

from __future__ import annotations

from celery import Task

from app.research.report import generate_report_for_ticker
from app.tasks.base import RETRY_KWARGS, job_task
from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, queue="interactive", name="generate_research_report", **RETRY_KWARGS)
def generate_research_report(
    self: Task, ticker: str, job_id: int, user_id: int | None = None
) -> str | None:
    with job_task(
        self,
        job_type="research_report",
        job_id=job_id,
        params={"ticker": ticker},
    ) as (session, progress):
        progress.update(progress=5, stage="gather-evidence")
        result = generate_report_for_ticker(session, ticker, user_id=user_id)
        progress.update(progress=95, stage="persist")
        return str(result.report_id) if result is not None else None
