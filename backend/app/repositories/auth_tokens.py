"""Single-use email-verify / password-reset token persistence (AUTH-003). Hashes only."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuthToken


def insert(
    session: Session, *, user_id: int, purpose: str, token_hash: str, expires_at: datetime
) -> AuthToken:
    row = AuthToken(user_id=user_id, purpose=purpose, token_hash=token_hash, expires_at=expires_at)
    session.add(row)
    session.flush()
    return row


def get_by_hash(session: Session, *, token_hash: str, purpose: str) -> AuthToken | None:
    return session.scalar(
        select(AuthToken).where(AuthToken.token_hash == token_hash, AuthToken.purpose == purpose)
    )


def recent_count(session: Session, *, user_id: int, purpose: str, since: datetime) -> int:
    """How many tokens of this purpose were issued to the user since `since` (rate limit)."""
    count = session.scalar(
        select(func.count())
        .select_from(AuthToken)
        .where(
            AuthToken.user_id == user_id,
            AuthToken.purpose == purpose,
            AuthToken.created_at >= since,
        )
    )
    return int(count or 0)


def mark_used(token: AuthToken, *, when: datetime) -> None:
    token.used_at = when
