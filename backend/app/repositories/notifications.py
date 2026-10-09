"""Notification persistence (§26.2, Phase 5d). User-scoped in-app records from alert dispatch."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Notification


def create(
    session: Session,
    *,
    user_id: int,
    alert_id: int | None,
    company_id: int | None,
    title: str,
    body: str | None,
    channel: str,
) -> Notification:
    row = Notification(
        user_id=user_id,
        alert_id=alert_id,
        company_id=company_id,
        title=title,
        body=body,
        channel=channel,
    )
    session.add(row)
    session.flush()
    return row


def list_for_user(
    session: Session, *, user_id: int, limit: int, after_id: int | None
) -> list[Notification]:
    """A user's notifications, newest first, keyset-paginated by descending id (API-002)."""
    conditions = [Notification.user_id == user_id]
    if after_id is not None:
        conditions.append(Notification.id < after_id)
    return list(
        session.scalars(
            select(Notification).where(*conditions).order_by(Notification.id.desc()).limit(limit)
        )
    )


def mark_read(session: Session, *, user_id: int, notification_id: int) -> bool:
    row = session.get(Notification, notification_id)
    if row is None or row.user_id != user_id:
        return False
    row.read_at = datetime.now(UTC)
    session.flush()
    return True
