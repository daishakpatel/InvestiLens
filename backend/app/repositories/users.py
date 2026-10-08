"""User persistence (spec §23.2, §26.1). All reads exclude soft-deleted/inactive rows by default."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def get_by_email(session: Session, email: str) -> User | None:
    """Any user with this email (including inactive/deleted); `email` is matched case-folded."""
    return session.scalar(select(User).where(User.email == email.lower()))


def get_active_by_email(session: Session, email: str) -> User | None:
    return session.scalar(
        select(User).where(
            User.email == email.lower(), User.is_active.is_(True), User.deleted_at.is_(None)
        )
    )


def get_active(session: Session, user_id: int) -> User | None:
    """Active, non-deleted user by id — the authenticated-principal lookup (AUTH-004)."""
    user = session.get(User, user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        return None
    return user


def create_user(
    session: Session,
    *,
    email: str,
    password_hash: str,
    role: str = "user",
    ai_budget_month_usd: Decimal | None = None,
) -> User:
    user = User(
        email=email.lower(),
        password_hash=password_hash,
        role=role,
        is_active=True,
        ai_budget_month_usd=ai_budget_month_usd,
    )
    session.add(user)
    session.flush()
    return user


def set_password(user: User, password_hash: str) -> None:
    user.password_hash = password_hash


def mark_email_verified(user: User) -> None:
    user.email_verified_at = datetime.now(UTC)


def soft_delete(user: User) -> None:
    """Mark the account deleted and inactive (LGL-007); a hard-delete job purges it later."""
    user.deleted_at = datetime.now(UTC)
    user.is_active = False


def hard_delete(session: Session, user_id: int) -> bool:
    """Permanently remove a user row (cascades to their data). The Phase 5d retention job path."""
    user = session.get(User, user_id)
    if user is None:
        return False
    session.delete(user)
    return True
