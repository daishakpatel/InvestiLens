"""Token primitives: HS256 access JWTs and opaque hashed refresh/verification tokens (AUTH-002).

Access tokens are stateless JWTs (claims sub/exp/iat/jti). Refresh and email-verify/reset tokens
are opaque 256-bit random values; only their SHA-256 hash is ever stored (ADR-0005). The JWT
secret comes from config and is never logged (SEC-001).
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.config import Settings, get_settings


class TokenError(Exception):
    """An access token is missing, malformed, expired, or has an invalid signature."""


def create_access_token(user_id: int, *, settings: Settings | None = None) -> tuple[str, int]:
    """Mint a short-lived access JWT; return (token, expires_in_seconds) (AUTH-002)."""
    settings = settings or get_settings()
    now = datetime.now(UTC)
    ttl = settings.access_token_ttl_seconds
    claims = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, ttl


def decode_access_token(token: str, *, settings: Settings | None = None) -> int:
    """Verify an access JWT and return its subject user id, or raise TokenError."""
    settings = settings or get_settings()
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return int(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise TokenError(str(exc)) from exc


def hash_token(raw: str) -> str:
    """SHA-256 hex digest used to store refresh / email tokens (never the raw value, AUTH-002)."""
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_refresh_token() -> tuple[str, str]:
    """Return (raw 256-bit token, its SHA-256 hash). The raw value goes to the client only."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def generate_opaque_token() -> tuple[str, str]:
    """A single-use email-verify / password-reset token: (raw, hash) (AUTH-003)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)
