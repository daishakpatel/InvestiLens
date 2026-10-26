"""Public demo abuse controls (Phase 7l Part B, NFR-ME-009, ADR-0050). Offline."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.middleware import RateLimitMiddleware, request_size_middleware
from app.config import get_settings
from app.providers import get_embedding_client, get_llm_client
from app.providers.mocks.embeddings import MockEmbeddingClient
from app.providers.mocks.llm import MockLLMClient
from tests.fakes import auth_headers


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)
    app.middleware("http")(request_size_middleware)

    @app.get("/api/v1/companies/TST")
    async def _read() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/v1/theses")
    async def _write() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_demo_mode_rate_limits_by_ip_even_with_rate_limits_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(settings, "rate_limit_backend", "memory")
    monkeypatch.setattr(settings, "rate_limit_per_minute", 2)
    client = TestClient(_app())
    # Every demo visitor shares one account, so two different tokens from one IP share a bucket.
    assert client.get("/api/v1/companies/TST", headers=auth_headers(1)).status_code == 200
    assert client.get("/api/v1/companies/TST", headers=auth_headers(2)).status_code == 200
    blocked = client.get("/api/v1/companies/TST", headers=auth_headers(3))
    assert blocked.status_code == 429 and blocked.headers["Retry-After"]


def test_oversized_bodies_are_refused_before_the_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "max_request_bytes", 1024)
    client = TestClient(_app())
    assert client.post("/api/v1/theses", content=b"x" * 1024).status_code == 200
    too_big = client.post("/api/v1/theses", content=b"x" * 1025)
    assert too_big.status_code == 413
    assert too_big.headers["content-type"].startswith("application/problem+json")
    assert "1024 bytes" in too_big.json()["detail"]
    assert client.get("/api/v1/companies/TST").status_code == 200  # reads are unaffected


def test_a_body_of_unknown_length_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "max_request_bytes", 1024)
    client = TestClient(_app())

    def chunks() -> Iterator[bytes]:
        yield b"x" * 10

    assert client.post("/api/v1/theses", content=chunks()).status_code == 411


def test_demo_mode_replays_recordings_whatever_the_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "embedding_provider", "voyage")
    assert isinstance(get_llm_client(), MockLLMClient)
    assert isinstance(get_embedding_client(), MockEmbeddingClient)
