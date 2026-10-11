"""Overlapping requests must not stall the API (NFR-001, ADR-0029). Real Postgres; skips offline.

The engine here has a single connection and the app two worker threads, with more requests than
either. Requests have to take turns; what must never happen is a request that holds one resource
while it waits for the other:

- waiting for a connection on the event loop, so the request holding it can never finish;
- keeping its connection after the handler returns, while it waits for a thread to serialise
  the response, with every thread taken by a handler waiting for that connection.

`get_db` prevents both by admitting only as many requests as there are connections.
"""

from __future__ import annotations

import asyncio
import time

import anyio.to_thread
import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import db
from app.main import app

_POOL_TIMEOUT_S = 3


@pytest.fixture(scope="module")
def _migrated(test_db_url: str) -> None:
    from tests.integration.conftest import _MIGRATIONS_DIR

    cfg = Config()
    cfg.set_main_option("script_location", _MIGRATIONS_DIR)
    cfg.set_main_option("sqlalchemy.url", test_db_url)
    command.upgrade(cfg, "head")


def test_overlapping_requests_share_a_small_pool_without_stalling(
    _migrated: None, test_db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = create_engine(test_db_url, pool_size=1, max_overflow=0, pool_timeout=_POOL_TIMEOUT_S)
    monkeypatch.setattr(db, "_session_factory", lambda: sessionmaker(bind=engine))
    monkeypatch.setattr(db, "_REQUEST_SLOTS", 1)  # as many as there are connections

    async def burst() -> list[httpx.Response]:
        anyio.to_thread.current_default_thread_limiter().total_tokens = 2  # this loop only
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # A search with no matches: one query and a serialised 200, with nothing to seed.
            url = "/api/v1/companies/search?q=zzzz"
            return await asyncio.gather(*(client.get(url) for _ in range(8)))

    try:
        started = time.monotonic()
        responses = asyncio.run(burst())
        elapsed = time.monotonic() - started
    finally:
        engine.dispose()

    assert [r.status_code for r in responses] == [200] * 8
    assert elapsed < _POOL_TIMEOUT_S, "a request waited out the pool timeout"
