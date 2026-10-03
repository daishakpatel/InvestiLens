"""Rate-limit middleware seam (ADR-0018, §24.1, §25.4).

Off by default; when enabled it applies an in-process token bucket keyed by client host and
returns an RFC 7807 429 on exhaustion. The in-process store is a stand-in — Phase 5c swaps the
backend for Redis and configures per-route limits behind this same middleware.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.api.errors import PROBLEM_MEDIA_TYPE
from app.config import get_settings
from app.schemas.common import Problem


class _TokenBucket:
    """A refilling token bucket: `capacity` tokens, refilled to full over 60s."""

    __slots__ = ("tokens", "updated")

    def __init__(self, capacity: float) -> None:
        self.tokens = capacity
        self.updated = time.monotonic()

    def allow(self, *, capacity: int) -> bool:
        now = time.monotonic()
        self.tokens = min(float(capacity), self.tokens + (now - self.updated) * (capacity / 60.0))
        self.updated = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-client-host token bucket. A no-op unless `rate_limit_enabled` is set."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._buckets: dict[str, _TokenBucket] = {}

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        bucket = self._buckets.setdefault(
            client, _TokenBucket(float(settings.rate_limit_per_minute))
        )
        if not bucket.allow(capacity=settings.rate_limit_per_minute):
            problem = Problem(
                title="Too Many Requests",
                status=429,
                detail="Rate limit exceeded; retry later.",
                instance=str(request.url),
                request_id=getattr(request.state, "request_id", None),
            )
            return JSONResponse(
                status_code=429,
                media_type=PROBLEM_MEDIA_TYPE,
                content=problem.model_dump(exclude_none=True),
            )
        return await call_next(request)
