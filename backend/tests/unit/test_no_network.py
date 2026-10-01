"""Assert the mock test run performs no outbound network I/O (Phase 0d DoD, DR-004).

Blocks outbound connections and DNS (not socket creation, which asyncio needs internally), then
exercises every mock provider. File I/O (fixtures) still works; any real egress raises.
"""

from __future__ import annotations

import asyncio
import socket

import pytest

from app.providers import (
    get_embedding_client,
    get_filings_provider,
    get_news_provider,
    get_price_provider,
)
from app.providers.base import LLMMessage
from app.providers.mocks.llm import MockLLMClient


class NoNetworkError(RuntimeError):
    pass


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked(*args: object, **kwargs: object) -> None:
        raise NoNetworkError("network egress is not allowed in the mock test run")

    # Block outbound connections + DNS. Socket creation stays available (asyncio self-pipe).
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)


def test_mocks_run_without_network(no_network: None) -> None:
    filings = get_filings_provider()
    assert asyncio.run(filings.resolve_company("NVDA")) is not None
    assert asyncio.run(filings.list_filings("0001045810"))
    assert asyncio.run(get_price_provider().get_prices("NVDA"))
    assert asyncio.run(get_news_provider().get_news("NVDA"))
    assert asyncio.run(get_embedding_client().embed(["hello"]))
    answer = asyncio.run(
        MockLLMClient().complete([LLMMessage("user", "hi")], model="claude-haiku-4-5", max_tokens=8)
    )
    assert answer


def test_network_guard_actually_blocks(no_network: None) -> None:
    with pytest.raises(NoNetworkError):
        socket.getaddrinfo("example.com", 443)
    with pytest.raises(NoNetworkError):
        socket.create_connection(("example.com", 443))
