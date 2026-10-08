"""FastAPI application factory (spec §24).

Wires the request-ID middleware (API-007), RFC 7807 error handlers (API-001), and every v1
router under `/api/v1`. In Phase 0c handlers return schema-shaped examples or `501`; real logic
arrives in later phases.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.api import (
    admin,
    auth,
    chat,
    companies,
    filings,
    health,
    research,
    sources,
    watchlist,
)
from app.api.errors import register_error_handlers
from app.api.middleware import RateLimitMiddleware
from app.api.security_headers import security_headers_middleware
from app.config import get_settings
from app.observability import metrics as metrics_module
from app.utils.logging import bind_request_id

API_V1_PREFIX = "/api/v1"
REQUEST_ID_HEADER = "X-Request-ID"


def create_app() -> FastAPI:
    app = FastAPI(
        title="InvestiLens API",
        version="1.0.0",
        description="Contract-first API for InvestiLens (spec §24).",
        openapi_url=f"{API_V1_PREFIX}/openapi.json",
    )

    # Middleware order matters: the LAST `add_middleware`/`@app.middleware` call is outermost
    # (runs first on the way in, last on the way out), so a response gets every layer's headers
    # and even a rate-limited/erroring request still gets a request id and CORS headers.
    app.add_middleware(RateLimitMiddleware)  # ADR-0018/0022

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Reuse an inbound request ID (API-007) or mint one; echo it on the response and bind it
        # to the logging context so every log line for this request correlates (NFR-015).
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        bind_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            bind_request_id(None)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    app.middleware("http")(metrics_module.api_latency_middleware)  # OBS-002
    app.middleware("http")(security_headers_middleware)  # SEC-004/012

    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,  # SEC-005: explicit allowlist, never "*"
        allow_credentials=True,  # the refresh-token cookie travels cross-origin in dev (Vite:5173)
        allow_methods=["GET", "POST", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-Next-Cursor"],
    )

    register_error_handlers(app)
    FastAPIInstrumentor.instrument_app(app)  # OBS-001: API-layer spans

    for module in (
        health,
        companies,
        filings,
        research,
        sources,
        chat,
        auth,
        watchlist,
        admin,
    ):
        app.include_router(module.router, prefix=API_V1_PREFIX)
    app.include_router(metrics_module.router)  # root-level /metrics (Prometheus scrape convention)

    return app


app = create_app()
