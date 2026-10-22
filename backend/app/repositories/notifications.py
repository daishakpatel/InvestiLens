"""Notification persistence (§26.2, Phase 5d). User-scoped in-app records from alert dispatch."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Notification


def create_once(
    session: Session,
    *,
    user_id: int,
    alert_id: int,
    company_id: int | None,
    event_key: str,
    title: str,
    body: str | None,
    channel: str,
    payload: dict[str, Any],
) -> int | None:
    """Insert unless this alert already has a row for `event_key` (FR-AL-007). Returns the new id,
    or None when the row existed: a re-run, or an overlapping run that got there first. A
    concurrent uncommitted insert of the same key makes this wait for it, then do nothing."""
    return session.scalar(
        pg_insert(Notification)
        .values(
            user_id=user_id,
            alert_id=alert_id,
            company_id=company_id,
            event_key=event_key,
            title=title[:256],
            body=body,
            channel=channel,
            payload=payload,
        )
        .on_conflict_do_nothing(index_elements=["alert_id", "event_key"])
        .returning(Notification.id)
    )


def delivered_event_keys(session: Session, *, alert_id: int, since: datetime) -> set[str]:
    """Event keys this alert already notified about since `since`, including the ones folded into
    a digest. Lets a retried run skip what an earlier, partly failed run delivered (FR-AL-008)."""
    keys: set[str] = set()
    for event_key, payload in session.execute(
        select(Notification.event_key, Notification.payload).where(
            Notification.alert_id == alert_id, Notification.created_at > since
        )
    ):
        if event_key:
            keys.add(event_key)
        keys.update((payload or {}).get("event_keys", []))
    return keys


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
