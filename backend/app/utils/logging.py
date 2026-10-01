"""Small structured-logging helper.

Emits log records with structured key/value context in the message's `extra`. A full structured
backend (structlog + JSON) arrives in Phase 5c; this keeps call sites structured meanwhile and
never logs secrets (conventions.md).
"""

from __future__ import annotations

import logging
from typing import Any


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    """Log `event` with structured `fields` (rendered as key=value)."""
    context = " ".join(f"{k}={v!r}" for k, v in fields.items())
    logger.log(level, "%s %s", event, context)
