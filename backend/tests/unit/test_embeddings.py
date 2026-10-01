"""Embedding provider + cost unit tests (Phase 2b). Offline — MockTransport + mock client.

Refs: EMB-001 (model/dim per row), EMB-002 (batch, cost log), ADR-0010 (Voyage), ADR-0013.
"""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.embeddings.pipeline import _cost
from app.providers.base import EmbeddingClient
from app.providers.mocks.embeddings import MOCK_MODEL, MockEmbeddingClient
from app.providers.voyage import VoyageEmbeddingClient
from app.utils.http import HardenedHttpClient


def _voyage_source(payload: dict[str, Any]) -> VoyageEmbeddingClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization", "").startswith("Bearer ")  # token in header
        assert "api.voyageai.com" in str(request.url)
        body = json.loads(request.content)
        assert body["input_type"] in {"document", "query"}  # ADR-0010
        return httpx.Response(200, content=json.dumps(payload).encode())

    inner = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": "t", "Authorization": "Bearer test"},
    )
    client = HardenedHttpClient(
        user_agent="t",
        allowed_hosts=frozenset({"api.voyageai.com"}),
        rate_per_sec=1000,
        client=inner,
    )
    return VoyageEmbeddingClient(client=client)


def test_voyage_parses_sorted_vectors_and_usage() -> None:  # EMB-001, EMB-002
    payload = {
        # deliberately out of order to prove we re-sort by `index`
        "data": [
            {"index": 1, "embedding": [0.0, 3.0, 4.0]},
            {"index": 0, "embedding": [3.0, 0.0, 4.0]},
        ],
        "usage": {"total_tokens": 42},
        "model": "voyage-finance-2",
    }
    client = _voyage_source(payload)
    vectors = asyncio.run(client.embed(["a", "b"], input_type="document"))
    assert len(vectors) == 2
    # index 0 came back second but must be first; vectors are L2-normalized (unit length).
    assert vectors[0][0] == pytest.approx(0.6) and vectors[0][2] == pytest.approx(0.8)
    assert sum(v * v for v in vectors[0]) == pytest.approx(1.0)
    assert client.last_total_tokens == 42  # provider usage captured for cost logging


def test_voyage_rejects_count_mismatch() -> None:
    client = _voyage_source({"data": [{"index": 0, "embedding": [1.0]}], "usage": {}})
    with pytest.raises(RuntimeError, match="vectors for"):
        asyncio.run(client.embed(["a", "b"]))


def test_voyage_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:  # ADR-0010
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("VOYAGE_API_KEY", "")
    monkeypatch.setenv("PROVIDER_MODE", "live")
    with pytest.raises(RuntimeError, match="VOYAGE_API_KEY"):
        VoyageEmbeddingClient()
    get_settings.cache_clear()


def test_voyage_empty_input_is_no_request() -> None:
    client = _voyage_source({"data": [], "usage": {"total_tokens": 7}})
    assert asyncio.run(client.embed([])) == []
    assert client.last_total_tokens == 0


def test_mock_default_model_is_backward_compatible() -> None:
    # Default-model vectors must be byte-identical to earlier phases (news dedup depends on them).
    default = MockEmbeddingClient()
    assert default.model_name == MOCK_MODEL
    v1 = asyncio.run(default.embed(["restricted cash"]))[0]
    v2 = asyncio.run(MockEmbeddingClient().embed(["restricted cash"]))[0]
    assert list(v1) == list(v2)


def test_mock_other_model_produces_different_vectors() -> None:  # EMB-003 migration realism
    old = MockEmbeddingClient()
    new = MockEmbeddingClient(model="mock-embed-v2")
    assert new.model_name == "mock-embed-v2"
    v_old = asyncio.run(old.embed(["gross margin"]))[0]
    v_new = asyncio.run(new.embed(["gross margin"]))[0]
    assert list(v_old) != list(v_new)  # a real model swap changes the vectors


def test_mock_is_an_embedding_client() -> None:
    assert isinstance(MockEmbeddingClient(), EmbeddingClient)


def test_cost_scales_with_tokens() -> None:  # EMB-002
    # 1M tokens at the default $0.12/1M == $0.12 exactly; cost is Decimal, never float.
    assert _cost(1_000_000) == Decimal("0.120000")
    assert _cost(0) == Decimal("0.000000")
    assert isinstance(_cost(500), Decimal)
