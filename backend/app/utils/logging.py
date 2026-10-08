"""Structured JSON logging (structlog), request-id correlation, and PII-safe redaction.

Keeps the exact call-site API every module already uses (`get_logger`, `log_event`,
`bind_request_id`) so this phase's structlog adoption (ADR-0021, spec §20) touches zero other
files. Under the hood: structlog renders JSON (OBS spec example in §28.1), `request_id` is bound
via `contextvars` so it auto-attaches to every log line on the task/request (API-007), and a
redaction processor drops any field whose key looks like a secret (OBS-004) so a stray debug field
can never leak a password/token/API key into logs.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, MutableMapping
from contextvars import ContextVar
from typing import Any, cast

import structlog

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_SENSITIVE_KEY = re.compile(r"password|secret|token|authorization|api_key", re.IGNORECASE)
_REDACTED = "***REDACTED***"


def _redact_sensitive(
    _logger: object, _name: str, event_dict: MutableMapping[str, Any]
) -> Mapping[str, Any]:
    """Mask any field whose key looks secret-shaped (OBS-004) — belt-and-suspenders."""
    for key in list(event_dict):
        if key != "event" and _SENSITIVE_KEY.search(key):
            event_dict[key] = _REDACTED
    return event_dict


def _configure() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,  # renders exc_info=True → a formatted traceback
            _redact_sensitive,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


_configure()


def bind_request_id(request_id: str | None) -> None:
    """Associate subsequent log lines on this task with `request_id` (API-007)."""
    _request_id.set(request_id)
    if request_id is None:
        structlog.contextvars.unbind_contextvars("request_id")
    else:
        structlog.contextvars.bind_contextvars(request_id=request_id)


def get_request_id() -> str | None:
    return _request_id.get()


def get_logger(name: str) -> structlog.typing.FilteringBoundLogger:
    return cast("structlog.typing.FilteringBoundLogger", structlog.get_logger(name))


_LEVEL_METHOD = {
    logging.DEBUG: "debug",
    logging.INFO: "info",
    logging.WARNING: "warning",
    logging.ERROR: "error",
    logging.CRITICAL: "critical",
}


def log_event(
    logger: structlog.typing.FilteringBoundLogger, level: int, event: str, **fields: Any
) -> None:
    """Log `event` as a structured JSON line with `fields` plus the bound request id."""
    method = _LEVEL_METHOD.get(level, "info")
    getattr(logger, method)(event, **fields)
