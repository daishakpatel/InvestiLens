"""eval_runs read + write access (spec §18, §24.2). Writes land here in Phase 5b."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EvalResult, EvalRun


def list_runs(session: Session, *, limit: int, after_id: int | None) -> list[EvalRun]:
    """Evaluation runs newest first, keyset-paginated by descending id."""
    conditions = [] if after_id is None else [EvalRun.id < after_id]
    return list(
        session.scalars(select(EvalRun).where(*conditions).order_by(EvalRun.id.desc()).limit(limit))
    )


def create_run(
    session: Session,
    *,
    name: str,
    config_hash: str,
    git_sha: str | None,
    metrics: dict[str, Any],
    status: str,
) -> EvalRun:
    """Persist one evaluation run's aggregate metrics (§18.5)."""
    run = EvalRun(
        name=name, config_hash=config_hash, git_sha=git_sha, metrics=metrics, status=status
    )
    session.add(run)
    session.flush()
    return run


def record_results(
    session: Session, *, run_id: int, results: list[tuple[str, dict[str, Any]]]
) -> None:
    """Bulk-insert per-question metrics for a run (no N+1)."""
    session.add_all(
        EvalResult(run_id=run_id, question_id=qid, metrics=metrics) for qid, metrics in results
    )
    session.flush()
