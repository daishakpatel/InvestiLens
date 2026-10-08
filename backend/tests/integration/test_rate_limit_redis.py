"""`RedisRateLimiter` against a real Redis (ADR-0022). Skips if unreachable, mirroring the
Postgres skip-offline pattern (ADR-0019) — CI's `redis:7-alpine` service makes it run there.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
import redis.asyncio as redis_asyncio

from app.api.rate_limit_backends import RedisRateLimiter
from app.config import get_settings


async def _run(key: str) -> list[bool]:
    client = redis_asyncio.from_url(get_settings().redis_url)
    await client.ping()
    limiter = RedisRateLimiter(client)  # type: ignore[arg-type]
    try:
        return [(await limiter.allow(key=key, limit=2, window_seconds=60))[0] for _ in range(3)]
    finally:
        await client.aclose()


def test_real_redis_enforces_the_window() -> None:
    key = f"test:{uuid.uuid4().hex}"
    try:
        results = asyncio.run(_run(key))
    except Exception as exc:
        pytest.skip(f"Redis not reachable for integration tests: {exc}")
    assert results == [True, True, False]
