"""The public demo's shared sandbox account (Phase 7l Part B, NFR-ME-007, ADR-0050).

In demo mode visitors cannot register; "Try the demo" signs them in as one shared user whose
writes (alerts, theses, watchlist) work normally and are wiped nightly by deleting the account,
which cascades to everything it owns. The account has no usable password.
"""

from __future__ import annotations

import secrets
import uuid

from sqlalchemy.orm import Session

from app.auth import passwords
from app.auth.service import IssuedTokens, _issue_tokens
from app.config import Settings, get_settings
from app.models import User
from app.repositories import users as user_repo

DEMO_EMAIL = "demo@example.com"  # RFC 2606: reserved, never a real inbox


def demo_user(session: Session) -> User:
    """The shared demo account, created on first use."""
    user = user_repo.get_active_by_email(session, DEMO_EMAIL)
    if user is None:
        # A random secret nobody knows: the account is reachable only through demo sign-in.
        user = user_repo.create_user(
            session, email=DEMO_EMAIL, password_hash=passwords.hash_password(secrets.token_hex(32))
        )
    return user


def demo_login(
    session: Session, *, user_agent: str | None, ip: str | None, settings: Settings | None = None
) -> IssuedTokens:
    settings = settings or get_settings()
    return _issue_tokens(
        session,
        demo_user(session),
        settings=settings,
        family_id=uuid.uuid4().hex,
        user_agent=user_agent,
        ip=ip,
    )


def reset_demo_sandbox(session: Session) -> bool:
    """Delete the shared account and its data; the next demo sign-in starts clean."""
    user = user_repo.get_by_email(session, DEMO_EMAIL)
    return user_repo.hard_delete(session, user.id) if user is not None else False
