"""Alert-rule persistence (spec §26.2). User-scoped CRUD; evaluation lives in `app/alerts`."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import Alert, Company


def list_for_user(session: Session, *, user_id: int) -> list[tuple[Alert, str | None]]:
    """(alert, ticker) pairs; ticker is None for a watchlist-wide alert."""
    rows = session.execute(
        select(Alert, Company.ticker)
        .outerjoin(Company, Company.id == Alert.company_id)
        .where(Alert.user_id == user_id)
        .order_by(Alert.id)
    )
    return [(alert, ticker) for alert, ticker in rows]


def count_for_user(session: Session, *, user_id: int) -> int:
    return session.scalar(select(func.count()).where(Alert.user_id == user_id)) or 0


def get_for_user(session: Session, *, user_id: int, alert_id: int) -> Alert | None:
    """None for another user's alert too, so the API answers 404 and leaks nothing (SEC-007)."""
    row = session.get(Alert, alert_id)
    return row if row is not None and row.user_id == user_id else None


def create(
    session: Session,
    *,
    user_id: int,
    company_id: int | None,
    event_type: str,
    params: dict[str, Any],
    channels: list[str],
    enabled: bool,
) -> Alert:
    row = Alert(
        user_id=user_id,
        company_id=company_id,
        event_type=event_type,
        params=params,
        channels=channels,
        enabled=enabled,
    )
    session.add(row)
    session.flush()
    session.refresh(row)  # created_at / watermark_at come from the database
    return row


def delete_for_user(session: Session, *, user_id: int, alert_id: int) -> bool:
    if get_for_user(session, user_id=user_id, alert_id=alert_id) is None:
        return False
    session.execute(delete(Alert).where(Alert.id == alert_id))
    return True
