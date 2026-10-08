"""RFC 7807 error handling (API-001, ERR-003). Offline — a throwaway FastAPI app, no DB.

The catch-all handler is the audit finding this phase: before it existed, an unhandled exception
bypassed RFC 7807 entirely and risked leaking a stack trace. This proves it never does.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import register_error_handlers


def _app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    async def _boom() -> None:
        raise ValueError("a very specific internal secret: db_password=hunter2")

    return app


def test_unhandled_exception_returns_generic_rfc7807_500() -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    resp = client.get("/boom")

    assert resp.status_code == 500
    assert resp.headers["content-type"] == "application/problem+json"
    body = resp.json()
    assert body["title"] == "Internal Server Error"
    assert body["status"] == 500
    # Nothing from the real exception ever reaches the response.
    assert "hunter2" not in resp.text
    assert "ValueError" not in resp.text
    assert "Traceback" not in resp.text
    assert "db_password" not in resp.text


def test_unhandled_exception_response_has_no_stack_trace_fields() -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    body = client.get("/boom").json()
    assert set(body.keys()) <= {"type", "title", "status", "detail", "instance", "request_id"}
