"""Security response headers (SEC-004/012): CSP, X-Content-Type-Options, frame-ancestors, HSTS.

This is a pure JSON API (SEC-004's "sanitize rendered filing HTML" doesn't apply here — the
frontend never uses `dangerouslySetInnerHTML`, enforced by a dedicated frontend guard test; see
`docs/security.md`). The headers below still matter for an API: `frame-ancestors 'none'` and
`X-Frame-Options: DENY` stop this API from being embedded and used for clickjacking against an
authenticated session, `X-Content-Type-Options: nosniff` stops a browser from executing a
JSON/CSV response as script if it's ever linked to directly, and HSTS pins HTTPS once the
deployment actually terminates TLS (`hsts_enabled`, off for local http dev — sending it over
plain HTTP is a no-op at best and a footgun at worst).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from app.config import get_settings

_CSP = "default-src 'none'; frame-ancestors 'none'"
# FastAPI's auto-generated interactive docs load swagger-ui/redoc JS+CSS from a CDN; a strict
# `default-src 'none'` CSP silently breaks them in a real browser (the HTML still loads — nothing
# in a server-side test catches this — but the scripts the page depends on do not). Exempt only
# these two paths; every actual API response keeps the strict policy.
_DOCS_PATHS = {"/docs", "/redoc"}


async def security_headers_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path not in _DOCS_PATHS:
        response.headers["Content-Security-Policy"] = _CSP
    response.headers["Referrer-Policy"] = "no-referrer"
    if get_settings().hsts_enabled:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response
