"""CORS allowlist (SEC-005). Offline — drives the real app's middleware stack, no DB needed for
a liveness-probe route."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_allowed_origin_gets_cors_headers() -> None:
    client = TestClient(app)
    resp = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_disallowed_origin_gets_no_cors_header() -> None:
    client = TestClient(app)
    resp = client.options(
        "/api/v1/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in resp.headers


def test_credentials_are_allowed_for_the_refresh_cookie_flow() -> None:
    client = TestClient(app)
    resp = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert resp.headers["access-control-allow-credentials"] == "true"
