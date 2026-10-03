"""Auth service: registration, login, refresh rotation, logout, deletion, verify/reset (§26.1).

Orchestrates passwords, tokens, the login throttle, and the user/refresh/auth-token repositories.
Transport concerns (cookies, HTTP status) live in the API layer; this module raises typed
`AuthError`s the router maps to responses.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.auth import passwords, tokens
from app.auth.ratelimit import LoginThrottle, login_throttle
from app.config import Settings, get_settings
from app.models import User
from app.repositories import auth_tokens as auth_token_repo
from app.repositories import refresh_tokens as refresh_repo
from app.repositories import users as user_repo

_VERIFY = "email_verify"
_RESET = "password_reset"
_MAX_EMAIL_TOKENS_PER_WINDOW = 3  # per user, per hour (AUTH-003 rate limit)


class AuthError(Exception):
    """Base auth failure with an HTTP status the router surfaces (RFC 7807)."""

    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EmailAlreadyRegistered(AuthError):
    status_code = 409


class InvalidCredentials(AuthError):
    status_code = 401


class AccountLocked(AuthError):
    status_code = 429


class InvalidToken(AuthError):
    status_code = 401


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    expires_in: int
    refresh_raw: str
    refresh_expires_at: datetime


def _issue_tokens(
    session: Session,
    user: User,
    *,
    settings: Settings,
    family_id: str,
    user_agent: str | None,
    ip: str | None,
) -> IssuedTokens:
    access, expires_in = tokens.create_access_token(user.id, settings=settings)
    raw, token_hash = tokens.generate_refresh_token()
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=settings.refresh_token_ttl_days)
    refresh_repo.insert(
        session,
        user_id=user.id,
        token_hash=token_hash,
        family_id=family_id,
        issued_at=now,
        expires_at=expires_at,
        user_agent=user_agent,
        ip=ip,
    )
    return IssuedTokens(
        access_token=access,
        expires_in=expires_in,
        refresh_raw=raw,
        refresh_expires_at=expires_at,
    )


def register(
    session: Session, *, email: str, password: str, settings: Settings | None = None
) -> User:
    """Create a new account (AUTH-001). Raises if the email is taken or the password is weak."""
    settings = settings or get_settings()
    passwords.validate_policy(password, settings=settings)
    if user_repo.get_by_email(session, email) is not None:
        raise EmailAlreadyRegistered("an account with this email already exists")
    user = user_repo.create_user(
        session, email=email, password_hash=passwords.hash_password(password)
    )
    # Issue a verification token so a row exists; delivery (email) is Phase 5d.
    request_email_verification(session, user, settings=settings)
    return user


def login(
    session: Session,
    *,
    email: str,
    password: str,
    user_agent: str | None,
    ip: str | None,
    settings: Settings | None = None,
    throttle: LoginThrottle | None = None,
) -> tuple[User, IssuedTokens]:
    """Authenticate and issue a fresh token family (AUTH-002/006)."""
    settings = settings or get_settings()
    throttle = throttle or login_throttle
    ip_key = f"ip:{ip or 'unknown'}"
    email_key = f"email:{email.lower()}"
    if throttle.any_locked(ip_key, email_key):
        raise AccountLocked("too many failed login attempts; try again later")

    user = user_repo.get_active_by_email(session, email)
    if user is None or not passwords.verify_password(password, user.password_hash):
        throttle.record_failure(ip_key)
        throttle.record_failure(email_key)
        raise InvalidCredentials("invalid email or password")

    throttle.clear(ip_key, email_key)
    if passwords.needs_rehash(user.password_hash):
        user_repo.set_password(user, passwords.hash_password(password))
    issued = _issue_tokens(
        session, user, settings=settings, family_id=uuid.uuid4().hex, user_agent=user_agent, ip=ip
    )
    return user, issued


def refresh(
    session: Session,
    *,
    raw_refresh: str | None,
    user_agent: str | None,
    ip: str | None,
    settings: Settings | None = None,
) -> tuple[User, IssuedTokens]:
    """Rotate a refresh token. Reuse of a revoked token revokes the whole family (AUTH-002)."""
    settings = settings or get_settings()
    if not raw_refresh:
        raise InvalidToken("missing refresh token")
    now = datetime.now(UTC)
    row = refresh_repo.get_by_hash(session, tokens.hash_token(raw_refresh))
    if row is None:
        raise InvalidToken("invalid refresh token")
    if row.revoked_at is not None:
        # Reuse of an already-rotated token → theft. Revoke the entire family (ADR-0005).
        refresh_repo.revoke_family(session, family_id=row.family_id, when=now)
        raise InvalidToken("refresh token reuse detected; session revoked")
    if row.expires_at <= now:
        refresh_repo.revoke(row, when=now)
        raise InvalidToken("refresh token expired")

    user = user_repo.get_active(session, row.user_id)
    if user is None:
        refresh_repo.revoke_family(session, family_id=row.family_id, when=now)
        raise InvalidToken("account unavailable")

    issued = _issue_tokens(
        session, user, settings=settings, family_id=row.family_id, user_agent=user_agent, ip=ip
    )
    new_row = refresh_repo.get_by_hash(session, tokens.hash_token(issued.refresh_raw))
    refresh_repo.revoke(row, when=now, replaced_by_id=new_row.id if new_row else None)
    return user, issued


def logout(session: Session, *, raw_refresh: str | None) -> None:
    """Revoke the presented token's whole family (idempotent; unknown tokens are a no-op)."""
    if not raw_refresh:
        return
    row = refresh_repo.get_by_hash(session, tokens.hash_token(raw_refresh))
    if row is not None:
        refresh_repo.revoke_family(session, family_id=row.family_id, when=datetime.now(UTC))


def delete_account(session: Session, user: User) -> None:
    """Soft-delete the account and revoke all its sessions (LGL-007)."""
    user_repo.soft_delete(user)
    refresh_repo.revoke_all_for_user(session, user_id=user.id, when=datetime.now(UTC))


def hard_delete_user(session: Session, user_id: int) -> bool:
    """Permanently purge a user and their data — the Phase 5d retention job path (LGL-007)."""
    return user_repo.hard_delete(session, user_id)


def _issue_email_token(session: Session, user: User, *, purpose: str, settings: Settings) -> str:
    window_start = datetime.now(UTC) - timedelta(hours=1)
    if (
        auth_token_repo.recent_count(session, user_id=user.id, purpose=purpose, since=window_start)
        >= _MAX_EMAIL_TOKENS_PER_WINDOW
    ):
        raise AccountLocked("too many token requests; try again later")
    raw, token_hash = tokens.generate_opaque_token()
    auth_token_repo.insert(
        session,
        user_id=user.id,
        purpose=purpose,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(hours=settings.email_token_ttl_hours),
    )
    return raw


def request_email_verification(
    session: Session, user: User, *, settings: Settings | None = None
) -> str:
    """Issue a single-use email-verification token; returns the raw value to be emailed."""
    return _issue_email_token(session, user, purpose=_VERIFY, settings=settings or get_settings())


def _consume(session: Session, *, raw: str, purpose: str) -> User:
    now = datetime.now(UTC)
    row = auth_token_repo.get_by_hash(session, token_hash=tokens.hash_token(raw), purpose=purpose)
    if row is None or row.used_at is not None or row.expires_at <= now:
        raise InvalidToken("invalid or expired token")
    user = user_repo.get_active(session, row.user_id)
    if user is None:
        raise InvalidToken("account unavailable")
    auth_token_repo.mark_used(row, when=now)
    return user


def confirm_email_verification(session: Session, *, raw: str) -> User:
    user = _consume(session, raw=raw, purpose=_VERIFY)
    user_repo.mark_email_verified(user)
    return user


def request_password_reset(
    session: Session, *, email: str, settings: Settings | None = None
) -> str | None:
    """Issue a reset token if the account exists; returns None otherwise (no enumeration)."""
    user = user_repo.get_active_by_email(session, email)
    if user is None:
        return None
    return _issue_email_token(session, user, purpose=_RESET, settings=settings or get_settings())


def confirm_password_reset(
    session: Session, *, raw: str, new_password: str, settings: Settings | None = None
) -> User:
    settings = settings or get_settings()
    passwords.validate_policy(new_password, settings=settings)
    user = _consume(session, raw=raw, purpose=_RESET)
    user_repo.set_password(user, passwords.hash_password(new_password))
    # Resetting the password invalidates every existing session (AUTH-002).
    refresh_repo.revoke_all_for_user(session, user_id=user.id, when=datetime.now(UTC))
    return user
