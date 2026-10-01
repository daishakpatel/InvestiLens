"""data_freshness persistence (FR-006, NFR-006): one row per (company, source)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DataFreshness


def record_freshness(
    session: Session,
    *,
    company_id: int,
    source: str,
    status: str,
    last_success_at: datetime | None,
    last_attempt_at: datetime,
    message: str | None = None,
) -> None:
    """Update the (company, source) freshness row, or insert it if absent."""
    row = session.scalar(
        select(DataFreshness).where(
            DataFreshness.company_id == company_id, DataFreshness.source == source
        )
    )
    if row is None:
        session.add(
            DataFreshness(
                company_id=company_id,
                source=source,
                status=status,
                last_success_at=last_success_at,
                last_attempt_at=last_attempt_at,
                message=message,
            )
        )
        return
    row.status = status
    row.last_attempt_at = last_attempt_at
    if last_success_at is not None:
        row.last_success_at = last_success_at
    row.message = message
