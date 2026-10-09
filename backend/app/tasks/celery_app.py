"""Celery application: three queues, retry policy, time limits (JOB-003/004, ADR-0024).

Queues (JOB-003):
- `interactive` — user-triggered, latency-sensitive (report generation). Run at higher
  concurrency so a long report never starves a quick one.
- `ingestion` — scheduled/poller data pulls (SEC, prices, news, parse, embed, metrics).
- `batch` — periodic housekeeping (eval suite, alert dispatch, retention purge).

Importing this module never opens a broker connection; only a worker or `.delay()` does, so the
API process imports it freely to enqueue. Tests flip `task_always_eager` on to run tasks inline
without a broker (see `conftest`).
"""

from __future__ import annotations

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "investilens",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.ingestion",
        "app.tasks.interactive",
        "app.tasks.batch",
        "app.tasks.schedule",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/New_York",  # JOB-006: market jobs are ET
    enable_utc=True,
    # JOB-004: a task that outlives the soft limit gets a catchable exception, then the hard kill.
    task_soft_time_limit=settings.celery_task_soft_time_limit_s,
    task_time_limit=settings.celery_task_time_limit_s,
    # JOB-001/004: redelivery on worker loss (visibility timeout) + at-least-once semantics; our
    # tasks are idempotent (ING-001), so redelivery is safe.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # fair dispatch for long interactive tasks
    task_track_started=True,  # JOB-002: STARTED state visible in the result backend
    broker_transport_options={"visibility_timeout": settings.celery_task_time_limit_s + 60},
    task_default_queue="batch",
    # Route each task to its queue by name prefix (set per-task via `queue=` on the decorator).
    worker_hijack_root_logger=False,  # keep structlog's JSON config (ADR-0021)
)
