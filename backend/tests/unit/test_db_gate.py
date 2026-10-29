"""The request gate in `get_db` turns a request away when no slot frees up (ADR-0029, NFR-001).

Offline: the gate is taken before any session is opened, so no database is needed.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app import db


def test_a_request_that_cannot_get_a_slot_is_a_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "_REQUEST_SLOTS", 0)  # every slot already taken
    monkeypatch.setattr(db, "_SLOT_WAIT_S", 0.01)

    async def first_step() -> None:
        await db.get_db().__anext__()

    with pytest.raises(HTTPException) as raised:
        asyncio.run(first_step())
    assert raised.value.status_code == 503
    assert raised.value.headers == {"Retry-After": "1"}
