"""Rate-limit backends (ADR-0022): the pluggable counter behind `RateLimitMiddleware`.

Split out from the middleware so the core fixed-window logic is unit-testable against a real
Redis wire protocol (`fakeredis`) without any middleware/ASGI machinery, and separately against a
real Redis in one integration test that skips if unreachable (mirrors the Postgres skip-offline
pattern, ADR-0019).
"""

from __future__ import annotations

import time
from typing import Protocol


class AsyncCounter(Protocol):
    """The slice of the Redis async client this needs — lets `fakeredis` stand in for real Redis."""

    async def incr(self, key: str) -> int: ...
    async def expire(self, key: str, seconds: int) -> bool: ...


class RedisRateLimiter:
    """A fixed-window request counter: `limit` requests per `window_seconds`, per key."""

    def __init__(self, client: AsyncCounter) -> None:
        self._client = client

    async def allow(self, *, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Returns `(allowed, retry_after_seconds)`. `retry_after` is 0 when allowed."""
        now = time.time()
        window = int(now // window_seconds)
        bucket_key = f"{key}:{window}"
        count = await self._client.incr(bucket_key)
        if count == 1:
            await self._client.expire(bucket_key, window_seconds)
        if count <= limit:
            return True, 0
        return False, window_seconds - int(now % window_seconds)


class MemoryRateLimiter:
    """A refilling token bucket per key — the in-process, test/CI-default backend (ADR-0018)."""

    __slots__ = ("_buckets",)

    def __init__(self) -> None:
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_updated)

    def allow(self, *, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = time.monotonic()
        tokens, updated = self._buckets.get(key, (float(limit), now))
        tokens = min(float(limit), tokens + (now - updated) * (limit / window_seconds))
        if tokens >= 1.0:
            self._buckets[key] = (tokens - 1.0, now)
            return True, 0
        self._buckets[key] = (tokens, now)
        return False, max(1, int(window_seconds / max(limit, 1)))
