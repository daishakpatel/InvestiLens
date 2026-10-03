"""Ingestion run + dead-letter persistence (ING-003, ING-004)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import IngestionDeadLetter, IngestionRun


def list_runs(session: Session, *, limit: int, after_id: int | None) -> list[IngestionRun]:
    """Ingestion runs newest first, keyset-paginated by descending id (admin, §24.2)."""
    conditions = [] if after_id is None else [IngestionRun.id < after_id]
    return list(
        session.scalars(
            select(IngestionRun).where(*conditions).order_by(IngestionRun.id.desc()).limit(limit)
        )
    )


def start_run(session: Session, *, source: str, company_id: int | None) -> IngestionRun:
    run = IngestionRun(
        source=source,
        company_id=company_id,
        started_at=datetime.now(UTC),
        status="running",
        counts={},
    )
    session.add(run)
    session.flush()
    return run


def finish_run(
    session: Session,
    run: IngestionRun,
    *,
    status: str,
    counts: dict[str, Any],
    error: str | None = None,
) -> None:
    run.status = status
    run.counts = counts
    run.error = error
    run.ended_at = datetime.now(UTC)


def dead_letter(session: Session, *, source: str, payload_ref: str, error: str) -> None:
    session.add(IngestionDeadLetter(source=source, payload_ref=payload_ref, error=error))
