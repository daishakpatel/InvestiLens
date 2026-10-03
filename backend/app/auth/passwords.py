"""Argon2id password hashing and policy (AUTH-001, ADR-0005).

Plaintext passwords are never logged or stored; only the Argon2id digest is persisted. The policy
is deliberately minimal for a portfolio project (a length floor), per the task file.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, VerifyMismatchError

from app.config import Settings, get_settings

# One shared hasher with library-default Argon2id parameters (sensible memory/time cost).
_hasher = PasswordHasher()


class WeakPasswordError(ValueError):
    """Raised when a password fails the policy (AUTH-001)."""


def validate_policy(password: str, *, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if len(password) < settings.password_min_length:
        raise WeakPasswordError(
            f"password must be at least {settings.password_min_length} characters"
        )


def hash_password(password: str) -> str:
    """Return the Argon2id digest of a password (the raw password is discarded after)."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time-ish verify via Argon2; False on any mismatch or malformed hash."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, Argon2Error):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True if the stored hash used older parameters and should be upgraded on next login."""
    return _hasher.check_needs_rehash(password_hash)
