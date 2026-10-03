"""Alert-rule persistence (spec §26.2). User-scoped CRUD; dispatch logic is Phase 5d."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Alert


def list_for_user(session: Session, *, user_id: int) -> list[Alert]:
    return list(session.scalars(select(Alert).where(Alert.user_id == user_id).order_by(Alert.id)))


def create(
    session: Session, *, user_id: int, company_id: int, alert_type: str, channel: str
) -> Alert:
    row = Alert(
        user_id=user_id,
        company_id=company_id,
        alert_type=alert_type,
        channel=channel,
        is_active=True,
    )
    session.add(row)
    session.flush()
    return row


def delete_for_user(session: Session, *, user_id: int, alert_id: int) -> bool:
    row = session.get(Alert, alert_id)
    if row is None or row.user_id != user_id:
        return False
    session.execute(delete(Alert).where(Alert.id == alert_id))
    return True
