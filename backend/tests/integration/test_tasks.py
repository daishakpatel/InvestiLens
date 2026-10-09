"""Background-job infrastructure tests (§25.1-2, JOB-001/002, ADR-0024). Real Postgres.

Covers the job-row lifecycle (`track_job`): running → done with progress (JOB-002), terminal
failure → `failed` dead-letter row (JOB-001), and a real Celery task run in eager mode that is
idempotent under a repeat (a redelivery/retry never double-fires).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Job
from app.repositories import jobs as job_repo
from app.tasks import base as task_base
from app.tasks.base import track_job
from app.tasks.batch import send_alerts
from app.tasks.celery_app import celery_app


@pytest.fixture(scope="module")
def _migrated(test_db_url: str) -> None:
    from tests.integration.conftest import _MIGRATIONS_DIR

    cfg = Config()
    cfg.set_main_option("script_location", _MIGRATIONS_DIR)
    cfg.set_main_option("sqlalchemy.url", test_db_url)
    command.upgrade(cfg, "head")


@pytest.fixture
def session(_migrated: None, test_engine: Engine) -> Iterator[Session]:
    with Session(test_engine) as s:
        yield s
        s.rollback()


def test_track_job_marks_done_with_progress(session: Session) -> None:
    with track_job(session, job_type="demo") as progress:
        progress.update(progress=50, stage="halfway")
    job = session.scalars(select(Job).where(Job.job_type == "demo")).one()
    assert job.status == "done" and job.progress == 100
    assert job.attempts == 1 and job.started_at is not None and job.ended_at is not None


def test_track_job_dead_letters_on_final_failure(session: Session) -> None:
    with (
        pytest.raises(RuntimeError),
        track_job(session, job_type="demo_fail", is_final_attempt=True),
    ):
        raise RuntimeError("boom")
    job = session.scalars(select(Job).where(Job.job_type == "demo_fail")).one()
    assert job.status == "failed"  # the failed row IS the dead-letter record (JOB-001)
    assert job.error is not None and "boom" in job.error


def test_track_job_retriable_failure_not_dead_lettered(session: Session) -> None:
    with (
        pytest.raises(RuntimeError),
        track_job(session, job_type="demo_retry", is_final_attempt=False),
    ):
        raise RuntimeError("transient")
    job = session.scalars(select(Job).where(Job.job_type == "demo_retry")).one()
    # Still 'running' (not failed) — it only dead-letters once retries are exhausted.
    assert job.status == "running"


def test_eager_task_runs_tracks_and_is_idempotent(
    _migrated: None, test_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real Celery task in eager mode: it runs inline, records a done `jobs` row, and a repeat
    run produces a second independent done row without error (idempotent, JOB-001/005)."""
    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)
    # Point the task's own session factory at the throwaway test DB (tasks run in the worker,
    # not under the request-scoped session).
    monkeypatch.setattr(task_base, "_session_factory", lambda: sessionmaker(bind=test_engine))

    result1 = send_alerts.apply().get()
    result2 = send_alerts.apply().get()
    assert result1 == 0 and result2 == 0  # no alerts seeded → nothing dispatched, no error

    with Session(test_engine) as s:
        done = job_repo.recent(s, limit=10)
        send_alert_jobs = [j for j in done if j.job_type == "send_alerts"]
        assert len(send_alert_jobs) >= 2
        assert all(j.status == "done" for j in send_alert_jobs)


def test_ingestion_queue_tasks_run_in_eager_mode(
    _migrated: None, test_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An ingestion-queue task runs end-to-end in eager mode and tracks its job (JOB-002/003)."""
    from app.tasks.ingestion import fetch_insider_and_holdings, generate_embeddings

    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(celery_app.conf, "task_eager_propagates", True)
    monkeypatch.setattr(task_base, "_session_factory", lambda: sessionmaker(bind=test_engine))

    # P2 no-op task: records a tracked job, returns its honest "not_implemented" status.
    insider = fetch_insider_and_holdings.apply(args=[["NVDA"]]).get()
    assert insider["status"] == "not_implemented"
    # Real pipeline fn over an empty test DB: nothing to embed → 0, no error.
    assert generate_embeddings.apply().get() == 0

    with Session(test_engine) as s:
        done = {j.job_type: j.status for j in job_repo.recent(s, limit=10)}
        assert done.get("fetch_insider_and_holdings") == "done"
        assert done.get("generate_embeddings") == "done"
