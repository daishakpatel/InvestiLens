"""Opaque keyset cursor pagination (API-002, ADR-0016).

A cursor is ``base64url(str(last_seen_id))``. Endpoints fetch ``limit + 1`` rows to learn whether
a next page exists, return the first ``limit``, and expose the next cursor either in a body field
(where the frozen Phase 0c contract already has one) or via the ``X-Next-Cursor`` response header
(keeping bare-array response shapes byte-identical to the contract — Phase 4a DoD #6).
"""

from __future__ import annotations

import base64

from app.api.errors import ProblemException
from app.config import get_settings

NEXT_CURSOR_HEADER = "X-Next-Cursor"


def decode_cursor(cursor: str | None) -> int | None:
    """Decode an opaque cursor to the last-seen id, or None for the first page.

    A malformed cursor is a 422 problem (API-001), never an unhandled crash.
    """
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        return int(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProblemException(
            422, "Invalid cursor", "The pagination cursor is malformed."
        ) from exc


def encode_cursor(last_id: int) -> str:
    return base64.urlsafe_b64encode(str(last_id).encode()).decode()


def clamp_limit(limit: int | None) -> int:
    """Clamp a requested page size to [1, api_max_page_size], defaulting when unset."""
    settings = get_settings()
    if limit is None:
        return settings.api_default_page_size
    return max(1, min(limit, settings.api_max_page_size))
