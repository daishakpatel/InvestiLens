"""eval_runs read access for the admin API (spec §18, §24.2). Eval writes land in Phase 5a."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EvalRun


def list_runs(session: Session, *, limit: int, after_id: int | None) -> list[EvalRun]:
    """Evaluation runs newest first, keyset-paginated by descending id."""
    conditions = [] if after_id is None else [EvalRun.id < after_id]
    return list(
        session.scalars(select(EvalRun).where(*conditions).order_by(EvalRun.id.desc()).limit(limit))
    )
