"""Offline unit tests for auth primitives (AUTH-001/002/006, ADR-0005)."""

from __future__ import annotations

import pytest

from app.auth import passwords, tokens
from app.auth.ratelimit import LoginThrottle
from app.auth.tokens import TokenError
from app.config import get_settings


def test_password_hash_is_argon2id_and_verifies() -> None:
    digest = passwords.hash_password("correct horse battery")
    assert digest.startswith("$argon2id$")  # AUTH-001
    assert "correct horse battery" not in digest  # never stores plaintext
    assert passwords.verify_password("correct horse battery", digest)
    assert not passwords.verify_password("wrong", digest)


def test_password_policy_enforces_min_length() -> None:
    with pytest.raises(passwords.WeakPasswordError):
        passwords.validate_policy("short")
    passwords.validate_policy("x" * get_settings().password_min_length)  # no raise


def test_access_token_round_trips() -> None:
    token, expires_in = tokens.create_access_token(123)
    assert expires_in == get_settings().access_token_ttl_seconds
    assert tokens.decode_access_token(token) == 123


def test_tampered_or_garbage_token_rejected() -> None:
    token, _ = tokens.create_access_token(1)
    with pytest.raises(TokenError):
        tokens.decode_access_token(token + "x")  # bad signature
    with pytest.raises(TokenError):
        tokens.decode_access_token("not.a.jwt")


def test_refresh_token_stored_as_hash_only() -> None:
    raw, digest = tokens.generate_refresh_token()
    assert raw != digest and len(digest) == 64  # sha-256 hex, raw never equals the stored value
    assert tokens.hash_token(raw) == digest


def test_login_throttle_locks_after_max_attempts() -> None:
    throttle = LoginThrottle()
    settings = get_settings()
    key = "email:a@example.com"
    for _ in range(settings.auth_login_max_attempts):
        assert not throttle.is_locked(key)
        throttle.record_failure(key)
    assert throttle.is_locked(key)  # AUTH-006
    throttle.clear(key)
    assert not throttle.is_locked(key)  # a successful login clears the counter
