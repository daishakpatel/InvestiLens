"""Ingestion run + dead-letter persistence (ING-003, ING-004)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import IngestionDeadLetter, IngestionRun


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
