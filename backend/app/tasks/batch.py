"""Batch-queue tasks (JOB-003): periodic housekeeping — alert dispatch, eval, retention purge."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from celery import Task

from app.alerts.dispatch import check_and_dispatch
from app.config import get_settings
from app.repositories.chat import purge_messages_before
from app.tasks.base import RETRY_KWARGS, job_task
from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, queue="batch", name="send_alerts", **RETRY_KWARGS)
def send_alerts(self: Task) -> int:
    """Evaluate every active alert and deliver notifications for any that fired (§26.2).

    Scheduled every few minutes so the DoD's 30-minute dispatch SLA holds even in the worst case
    (EDGAR poll ≤10 min to ingest + this to notice)."""
    with job_task(self, job_type="send_alerts") as (session, _progress):
        return check_and_dispatch(session)


@celery_app.task(bind=True, queue="batch", name="purge_chat_history", **RETRY_KWARGS)
def purge_chat_history(self: Task) -> int:
    """Delete chat messages past the retention window (SEC-014)."""
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(days=settings.chat_message_retention_days)
    with job_task(self, job_type="purge_chat_history") as (session, _progress):
        return purge_messages_before(session, cutoff=cutoff)


@celery_app.task(bind=True, queue="batch", name="run_eval_suite", **RETRY_KWARGS)
def run_eval_suite(self: Task, *, smoke: bool = True, user_id: int = 1) -> int:
    """Nightly evaluation run (§18, Phase 5b). Persists an `eval_runs` row; returns its id.

    Deferred import of the eval stack keeps Celery worker start-up light and avoids importing the
    judge/LLM wiring in processes that never run evals.
    """
    from app.eval.dataset import load_golden
    from app.eval.judge import JUDGE_PROMPT_VERSION, FakeJudge, LLMJudge
    from app.eval.runner import config_hash, persist_run, run_eval
    from app.providers import get_llm_client

    settings = get_settings()
    judge = (
        LLMJudge(get_llm_client(), model=settings.llm_model_strong)
        if settings.provider_mode == "live"
        else FakeJudge()
    )
    smoke_path = None
    if smoke:
        from pathlib import Path

        smoke_path = Path(__file__).resolve().parents[2] / "tests" / "eval" / "smoke.jsonl"
    questions = load_golden(smoke_path)
    with job_task(self, job_type="run_eval_suite", params={"smoke": smoke}) as (session, _p):
        summary = run_eval(session, questions, user_id=user_id, llm=get_llm_client(), judge=judge)
        return persist_run(
            session,
            summary,
            name="smoke" if smoke else "full",
            config_hash=config_hash(settings, judge_version=JUDGE_PROMPT_VERSION),
            git_sha=None,
        )
