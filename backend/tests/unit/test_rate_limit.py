"""Rate-limit backend + middleware tests (§25.4, SEC-008, ADR-0018/0022).

`MemoryRateLimiter` and the middleware wiring run fully offline. `RedisRateLimiter` is tested
against `fakeredis` — a real wire-protocol implementation in memory, not a stub — so the actual
`INCR`/`EXPIRE` fixed-window logic is exercised without a live Redis (ADR-0022).
"""

from __future__ import annotations

import asyncio
import time
from typing import cast

import fakeredis.aioredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.middleware import RateLimitMiddleware
from app.api.rate_limit_backends import AsyncCounter, MemoryRateLimiter, RedisRateLimiter
from app.config import get_settings


def _fake_redis_counter() -> AsyncCounter:
    return cast("AsyncCounter", fakeredis.aioredis.FakeRedis())


def test_memory_limiter_allows_then_blocks() -> None:
    limiter = MemoryRateLimiter()
    allowed = [limiter.allow(key="k", limit=3, window_seconds=60)[0] for _ in range(4)]
    assert allowed == [True, True, True, False]


def test_memory_limiter_keys_are_independent() -> None:
    limiter = MemoryRateLimiter()
    for _ in range(3):
        assert limiter.allow(key="a", limit=3, window_seconds=60)[0]
    # A different key starts with its own full bucket.
    assert limiter.allow(key="b", limit=3, window_seconds=60)[0]


def test_redis_limiter_allows_then_blocks() -> None:
    async def _run() -> list[tuple[bool, int]]:
        limiter = RedisRateLimiter(_fake_redis_counter())
        return [await limiter.allow(key="k", limit=2, window_seconds=60) for _ in range(3)]

    results = asyncio.run(_run())
    assert [r[0] for r in results] == [True, True, False]
    assert results[2][1] > 0  # retry_after is positive once blocked


def test_redis_limiter_window_resets() -> None:
    async def _run() -> tuple[bool, bool, bool]:
        limiter = RedisRateLimiter(_fake_redis_counter())
        first = (await limiter.allow(key="k", limit=1, window_seconds=1))[0]
        second = (await limiter.allow(key="k", limit=1, window_seconds=1))[0]
        time.sleep(1.1)
        third = (await limiter.allow(key="k", limit=1, window_seconds=1))[0]
        return first, second, third

    assert asyncio.run(_run()) == (True, False, True)


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/api/v1/companies/TST")
    async def _read() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/v1/chat")
    async def _chat() -> dict[str, bool]:
        return {"ok": True}

    return app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_backend", "memory")
    monkeypatch.setattr(settings, "rate_limit_per_minute", 2)
    monkeypatch.setattr(settings, "rate_limit_ai_per_hour", 1)
    return TestClient(_app())


def test_general_route_blocked_after_limit(client: TestClient) -> None:
    assert client.get("/api/v1/companies/TST").status_code == 200
    assert client.get("/api/v1/companies/TST").status_code == 200
    blocked = client.get("/api/v1/companies/TST")
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After") is not None
    assert blocked.json()["title"] == "Too Many Requests"


def test_ai_route_has_its_own_tighter_tier(client: TestClient) -> None:
    """The AI tier (1/hour here) is separate from — and tighter than — the general tier (2/min)."""
    assert client.post("/api/v1/chat").status_code == 200
    blocked = client.post("/api/v1/chat")
    assert blocked.status_code == 429
    # The general route is unaffected: the AI bucket is a different key.
    assert client.get("/api/v1/companies/TST").status_code == 200


def test_disabled_by_default_is_a_no_op(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    c = TestClient(_app())
    for _ in range(10):
        assert c.get("/api/v1/companies/TST").status_code == 200
