"""Security response headers (SEC-004/012). Offline — a throwaway FastAPI app, no DB."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.security_headers import security_headers_middleware


def _app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(security_headers_middleware)

    @app.get("/thing")
    async def _thing() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_security_headers_present_on_api_responses() -> None:
    client = TestClient(_app())
    resp = client.get("/thing")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert "Strict-Transport-Security" not in resp.headers  # hsts_enabled defaults False


def test_csp_exempts_interactive_docs_pages() -> None:
    """A strict CSP would silently break FastAPI's CDN-loaded Swagger UI/ReDoc in a real browser."""
    client = TestClient(_app())
    assert "Content-Security-Policy" not in client.get("/docs").headers
    assert "Content-Security-Policy" not in client.get("/redoc").headers
    # Every other path keeps the strict policy, including the API itself.
    assert "Content-Security-Policy" in client.get("/thing").headers


def test_hsts_sent_only_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "hsts_enabled", True)
    resp = TestClient(_app()).get("/thing")
    assert resp.headers["Strict-Transport-Security"] == "max-age=63072000; includeSubDomains"
