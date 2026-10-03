"""Refresh-token persistence (AUTH-002, ADR-0005). Only token hashes are stored, never raw values.

Tokens belong to a `family_id` (one rotation chain). Rotation revokes the presented token and
issues its successor; presenting an already-revoked token is reuse (theft) and revokes the whole
family.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CursorResult, select, update
from sqlalchemy.orm import Session

from app.models import RefreshToken


def _rowcount(result: object) -> int:
    assert isinstance(result, CursorResult)  # noqa: S101  # UPDATE always yields a CursorResult
    return result.rowcount


def insert(
    session: Session,
    *,
    user_id: int,
    token_hash: str,
    family_id: str,
    issued_at: datetime,
    expires_at: datetime,
    user_agent: str | None,
    ip: str | None,
) -> RefreshToken:
    row = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        family_id=family_id,
        issued_at=issued_at,
        expires_at=expires_at,
        user_agent=user_agent,
        ip=ip,
    )
    session.add(row)
    session.flush()
    return row


def get_by_hash(session: Session, token_hash: str) -> RefreshToken | None:
    return session.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))


def revoke(token: RefreshToken, *, when: datetime, replaced_by_id: int | None = None) -> None:
    token.revoked_at = when
    if replaced_by_id is not None:
        token.replaced_by_id = replaced_by_id


def revoke_family(session: Session, *, family_id: str, when: datetime) -> int:
    """Revoke every still-active token in a family (reuse detection / logout / password reset)."""
    result = session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=when)
    )
    return _rowcount(result)


def revoke_all_for_user(session: Session, *, user_id: int, when: datetime) -> int:
    """Revoke all active refresh tokens for a user (account deletion / password reset)."""
    result = session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=when)
    )
    return _rowcount(result)
