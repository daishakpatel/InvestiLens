"""FastAPI application factory (spec §24).

Wires the request-ID middleware (API-007), RFC 7807 error handlers (API-001), and every v1
router under `/api/v1`. In Phase 0c handlers return schema-shaped examples or `501`; real logic
arrives in later phases.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

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

API_V1_PREFIX = "/api/v1"
REQUEST_ID_HEADER = "X-Request-ID"


def create_app() -> FastAPI:
    app = FastAPI(
        title="InvestiLens API",
        version="1.0.0",
        description="Contract-first API for InvestiLens (spec §24).",
        openapi_url=f"{API_V1_PREFIX}/openapi.json",
    )

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Reuse an inbound request ID (API-007) or mint one; echo it on the response.
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    register_error_handlers(app)

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

    return app


app = create_app()
