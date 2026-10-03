"""Small structured-logging helper.

Emits log records with structured key/value context in the message's `extra`. A full structured
backend (structlog + JSON) arrives in Phase 5c; this keeps call sites structured meanwhile and
never logs secrets (conventions.md).

The request-id contextvar (API-007) lets any log line correlate to the inbound request without
threading the id through every call; the API middleware binds it per request.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def bind_request_id(request_id: str | None) -> None:
    """Associate subsequent log lines on this task with `request_id` (API-007)."""
    _request_id.set(request_id)


def get_request_id() -> str | None:
    return _request_id.get()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    """Log `event` with structured `fields` (rendered as key=value), plus the bound request id."""
    request_id = _request_id.get()
    if request_id is not None and "request_id" not in fields:
        fields = {"request_id": request_id, **fields}
    context = " ".join(f"{k}={v!r}" for k, v in fields.items())
    logger.log(level, "%s %s", event, context)
