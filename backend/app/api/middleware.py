"""Rate-limit middleware (ADR-0018 seam, completed by ADR-0022, §24.1, §25.4).

Off by default (`rate_limit_enabled`). Two tiers, both per-user when authenticated (falling back
to client IP for anonymous requests, per spec §25.4): a general `rate_limit_per_minute` (default
100, the spec's own example) on every route, and a tighter `rate_limit_ai_per_hour` (default 20)
on the AI-cost endpoints (`/chat*`, `POST /research`). The backend is `"memory"` (in-process,
deterministic — the test/CI default, ADR-0018) or `"redis"` (real cross-worker limiting via
`REDIS_URL`, ADR-0022) — see `app.api.rate_limit_backends` for the counters themselves.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.api.errors import PROBLEM_MEDIA_TYPE
from app.api.rate_limit_backends import AsyncCounter, MemoryRateLimiter, RedisRateLimiter
from app.auth.tokens import TokenError, decode_access_token
from app.config import Settings, get_settings
from app.schemas.common import Problem

_AI_PATH_PREFIXES = ("/api/v1/chat", "/api/v1/research")


def _is_ai_route(path: str) -> bool:
    return path.startswith(_AI_PATH_PREFIXES)


def _identity(request: Request) -> str:
    """`user:<id>` when the bearer token decodes cleanly, else `ip:<host>` (spec §25.4)."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            return f"user:{decode_access_token(auth[len('Bearer ') :])}"
        except TokenError:
            pass
    client = request.client.host if request.client else "unknown"
    return f"ip:{client}"


def _tier(path: str, settings: Settings) -> tuple[str, int, int]:
    """(bucket_prefix, limit, window_seconds) for this request's path."""
    if _is_ai_route(path):
        return "ai", settings.rate_limit_ai_per_hour, 3600
    return "min", settings.rate_limit_per_minute, 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-identity, per-tier rate limiting. A no-op unless `rate_limit_enabled` is set."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._memory = MemoryRateLimiter()
        self._redis_limiter: RedisRateLimiter | None = None

    def _get_redis_limiter(self, settings: Settings) -> RedisRateLimiter:
        if self._redis_limiter is None:
            import redis.asyncio as redis_asyncio

            client = cast("AsyncCounter", redis_asyncio.from_url(settings.redis_url))
            self._redis_limiter = RedisRateLimiter(client)
        return self._redis_limiter

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return await call_next(request)

        prefix, limit, window = _tier(request.url.path, settings)
        bucket_key = f"{prefix}:{_identity(request)}"
        if settings.rate_limit_backend == "redis":
            allowed, retry_after = await self._get_redis_limiter(settings).allow(
                key=bucket_key, limit=limit, window_seconds=window
            )
        else:
            allowed, retry_after = self._memory.allow(
                key=bucket_key, limit=limit, window_seconds=window
            )
        if not allowed:
            problem = Problem(
                title="Too Many Requests",
                status=429,
                detail=f"Rate limit exceeded; retry in {retry_after}s.",
                instance=str(request.url),
                request_id=getattr(request.state, "request_id", None),
            )
            return JSONResponse(
                status_code=429,
                media_type=PROBLEM_MEDIA_TYPE,
                content=problem.model_dump(exclude_none=True),
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)
