"""Background-job persistence (spec §25.1, ADR-0017).

A `jobs` row tracks an async request (research generation, company refresh) through
queued → running → done/failed. The Phase 5d worker executes queued jobs; Phase 4a only enqueues
and single-flights them. `params` carries the idempotency key and request inputs so a duplicate
request can attach to an existing job (JOB-005).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job

_NON_TERMINAL = ("queued", "running")


def create_job(
    session: Session,
    *,
    job_type: str,
    params: dict[str, Any],
    created_by: int | None = None,
    result_ref: str | None = None,
) -> Job:
    job = Job(
        job_type=job_type,
        params=params,
        status="queued",
        progress=0,
        result_ref=result_ref,
        created_by=created_by,
        started_at=datetime.now(UTC),
    )
    session.add(job)
    session.flush()
    return job


def get_job(session: Session, job_id: int) -> Job | None:
    return session.get(Job, job_id)


def find_by_idempotency_key(session: Session, *, job_type: str, key: str) -> Job | None:
    """An existing job created under this idempotency key (API-003 single-flight)."""
    return session.scalar(
        select(Job)
        .where(Job.job_type == job_type, Job.params["idempotency_key"].astext == key)
        .order_by(Job.id.desc())
    )


def find_active_for_company(session: Session, *, job_type: str, ticker: str) -> Job | None:
    """A still-running job for the same company, so a duplicate request attaches to it (JOB-005)."""
    return session.scalar(
        select(Job)
        .where(
            Job.job_type == job_type,
            Job.status.in_(_NON_TERMINAL),
            Job.params["ticker"].astext == ticker,
        )
        .order_by(Job.id.desc())
    )
