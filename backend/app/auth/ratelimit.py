"""Login throttle: per-account and per-IP failure counting with lockout (AUTH-006).

In-process, like the rate-limit middleware seam (ADR-0018); Phase 5c moves the store to Redis. A
key (an email or an IP) that accrues `max_attempts` failures inside `window_seconds` is locked out
for `lockout_seconds`. A successful login clears the key.
"""

from __future__ import annotations

import time

from app.config import Settings, get_settings


class LoginThrottle:
    """Sliding-window failure counter with a lockout, keyed by an arbitrary string."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._failures: dict[str, list[float]] = {}
        self._locked_until: dict[str, float] = {}

    def _now(self) -> float:
        return time.monotonic()

    def is_locked(self, key: str) -> bool:
        until = self._locked_until.get(key)
        if until is None:
            return False
        if self._now() >= until:
            # Lock expired: clear it so the caller gets a fresh window.
            self._locked_until.pop(key, None)
            self._failures.pop(key, None)
            return False
        return True

    def any_locked(self, *keys: str) -> bool:
        return any(self.is_locked(k) for k in keys)

    def record_failure(self, key: str) -> None:
        now = self._now()
        window = self._settings.auth_login_window_seconds
        recent = [t for t in self._failures.get(key, []) if now - t < window]
        recent.append(now)
        self._failures[key] = recent
        if len(recent) >= self._settings.auth_login_max_attempts:
            self._locked_until[key] = now + self._settings.auth_login_lockout_seconds

    def clear(self, *keys: str) -> None:
        for key in keys:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)


# Process-wide throttle used by the auth service; tests construct their own instance.
login_throttle = LoginThrottle()
