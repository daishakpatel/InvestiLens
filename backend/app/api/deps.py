"""Shared FastAPI auth dependencies (Phase 4b, §26.1, AUTH-004).

The authenticated principal is resolved from a verified `Authorization: Bearer <access JWT>`
(ADR-0005). `get_current_user_id`/`require_admin` keep their `-> int` signatures so Phase 4a call
sites (chat, watchlists, alerts, admin) are untouched — this swaps the X-User-Id seam for real
JWT verification without changing them.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.tokens import TokenError, decode_access_token
from app.db import get_db
from app.models import User
from app.repositories import users as user_repo

_DB = Depends(get_db)
_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="authentication required",
    headers={"WWW-Authenticate": "Bearer"},
)


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _UNAUTHENTICATED
    return authorization[7:].strip()


def get_current_user(authorization: str | None = Header(default=None), db: Session = _DB) -> User:
    """The active user behind a valid access token, or 401 (AUTH-004)."""
    token = _bearer_token(authorization)
    try:
        user_id = decode_access_token(token)
    except TokenError as exc:
        raise _UNAUTHENTICATED from exc
    user = user_repo.get_active(db, user_id)
    if user is None:
        raise _UNAUTHENTICATED
    return user


_CURRENT_USER = Depends(get_current_user)


def get_current_user_id(user: User = _CURRENT_USER) -> int:
    return user.id


def require_admin(user: User = _CURRENT_USER) -> int:
    """Admin-only routes (SEC-007); the access token's user must have role ``admin``."""
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin role required")
    return user.id
