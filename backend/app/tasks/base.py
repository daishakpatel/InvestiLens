"""Shared task plumbing: job-row tracking (JOB-002) and the retry policy (JOB-001).

Every task body runs inside `track_job(...)`, which owns the `jobs`-row lifecycle — create or
adopt a row, mark it running, let the body report progress/stage, and mark it done or failed.
On a terminal failure (retries exhausted) the failed `jobs` row *is* the dead-letter record
(JOB-001): it carries the error and is queryable, alertable (OBS-003), and replayable.

`RETRY_KWARGS` is applied to every task decorator so retries are uniform: exponential backoff
with jitter, capped, bounded attempts (JOB-001). Because our task bodies are idempotent
(ING-001, upserts/replace-per-company), a redelivered or retried task never double-writes.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from celery import Task
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import _session_factory
from app.repositories import jobs as job_repo
from app.utils.logging import get_logger, log_event

logger = get_logger(__name__)

# Applied to every @celery_app.task (JOB-001). Celery computes delay = backoff * 2**retries with
# jitter, capped at retry_backoff_max; autoretry_for=(Exception,) covers any transient failure.
RETRY_KWARGS: dict[str, Any] = {
    "autoretry_for": (Exception,),
    "retry_backoff": True,  # exponential
    "retry_backoff_max": 600,
    "retry_jitter": True,
    "max_retries": get_settings().celery_max_retries,
    "acks_late": True,
}


@dataclass
class JobProgress:
    """Handed to a task body so it can emit progress/stage events (JOB-002)."""

    _session: Session
    _job: Any

    def update(self, *, progress: int, stage: str | None = None) -> None:
        job_repo.set_progress(self._session, self._job, progress=progress, stage=stage)
        # Commit so a polling client / SSE sees the progress event mid-run (JOB-002).
        self._session.commit()


@contextmanager
def track_job(
    session: Session,
    *,
    job_type: str,
    params: dict[str, Any] | None = None,
    job_id: int | None = None,
    created_by: int | None = None,
    is_final_attempt: bool = True,
) -> Iterator[JobProgress]:
    """Own the `jobs`-row lifecycle around a task body.

    `job_id` adopts a pre-created row (e.g. the one `POST /research` already made); otherwise a
    fresh row is created for this run. `is_final_attempt` controls terminal bookkeeping: on a
    retriable attempt we re-raise without marking the row `failed`, so the row only becomes a
    dead-letter once Celery has exhausted its retries.
    """
    if job_id is not None:
        job = job_repo.get_job(session, job_id)
        if job is None:
            raise ValueError(f"job {job_id} not found")
    else:
        job = job_repo.create_job(
            session, job_type=job_type, params=params or {}, created_by=created_by
        )
    job_repo.mark_running(session, job)
    session.commit()
    try:
        yield JobProgress(session, job)
    except Exception as exc:
        session.rollback()
        if is_final_attempt:
            job_repo.mark_failed(session, job, error=f"{type(exc).__name__}: {exc}")
            session.commit()
            log_event(
                logger,
                logging.ERROR,
                "job.dead_letter",
                job_type=job_type,
                job_id=job.id,
                error=str(exc),
            )
        else:
            log_event(
                logger,
                logging.WARNING,
                "job.retrying",
                job_type=job_type,
                job_id=job.id,
                error=str(exc),
            )
        raise
    else:
        job_repo.mark_done(session, job)
        session.commit()
        log_event(logger, logging.INFO, "job.done", job_type=job_type, job_id=job.id)


@contextmanager
def job_task(
    task: Task,
    *,
    job_type: str,
    params: dict[str, Any] | None = None,
    job_id: int | None = None,
    created_by: int | None = None,
) -> Iterator[tuple[Session, JobProgress]]:
    """The per-task preamble: a DB session + a tracked `jobs` row, with `is_final_attempt`
    derived from Celery's retry counter so the row only dead-letters once retries are spent.

    `task` is the bound Celery task (`@task(bind=True)`), giving `request.retries`/`max_retries`.
    The session is this module's own (not the request-scoped FastAPI one): tasks run in the worker.
    """
    is_final = (task.request.retries or 0) >= (task.max_retries or 0)
    session = _session_factory()()
    try:
        with track_job(
            session,
            job_type=job_type,
            params=params,
            job_id=job_id,
            created_by=created_by,
            is_final_attempt=is_final,
        ) as progress:
            yield session, progress
    finally:
        session.close()
