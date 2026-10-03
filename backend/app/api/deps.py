"""Shared FastAPI dependencies.

`get_current_user_id` is the authenticated-user seam. Chat requires an account (ADR-0006), but JWT
auth is Phase 4b; until then the user id is read from an `X-User-Id` header so the chat flow is
callable and testable. Phase 4b replaces this with token verification without changing call sites.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status


def get_current_user_id(x_user_id: int | None = Header(default=None)) -> int:
    if x_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required (chat needs an account, ADR-0006)",
        )
    return x_user_id
