"""Auth endpoints (spec §24.2, §26.1): registration, login, token rotation, logout, account.

Access tokens are returned in the body; the rotating refresh token is set in an httpOnly, Secure,
SameSite=Strict cookie scoped to this path (AUTH-002, ADR-0005). Email-verification and
password-reset are minimal single-use-token flows (AUTH-003); email delivery is Phase 5d, so the
`request` endpoints acknowledge without leaking whether an account exists.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.auth import service
from app.auth.service import IssuedTokens
from app.config import Settings, get_settings
from app.db import get_db
from app.models import User
from app.schemas.auth import (
    AuthMessage,
    EmailVerifyConfirm,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    TokenResponse,
    UserProfile,
)

router = APIRouter(prefix="/auth", tags=["Auth"])

_DB = Depends(get_db)
_CURRENT_USER = Depends(get_current_user)


def _profile(user: User) -> UserProfile:
    return UserProfile(
        id=str(user.id),
        email=user.email,
        role=user.role,
        email_verified=user.email_verified_at is not None,
    )


def _set_refresh_cookie(response: Response, issued: IssuedTokens, settings: Settings) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=issued.refresh_raw,
        max_age=settings.refresh_token_ttl_days * 86400,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="strict",
        path=settings.refresh_cookie_path,
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(key=settings.refresh_cookie_name, path=settings.refresh_cookie_path)


def _token_response(issued: IssuedTokens) -> TokenResponse:
    return TokenResponse(access_token=issued.access_token, expires_in=issued.expires_in)


@router.post("/register", status_code=201, response_model=UserProfile)
async def register(body: RegisterRequest, db: Session = _DB) -> UserProfile:
    user = service.register(db, email=body.email, password=body.password)
    db.commit()
    return _profile(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, request: Request, response: Response, db: Session = _DB
) -> TokenResponse:
    _, issued = service.login(
        db,
        email=body.email,
        password=body.password,
        user_agent=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )
    db.commit()
    _set_refresh_cookie(response, issued, get_settings())
    return _token_response(issued)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response, db: Session = _DB) -> TokenResponse:
    settings = get_settings()
    raw = request.cookies.get(settings.refresh_cookie_name)
    _, issued = service.refresh(
        db,
        raw_refresh=raw,
        user_agent=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )
    db.commit()
    _set_refresh_cookie(response, issued, settings)
    return _token_response(issued)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, db: Session = _DB) -> None:
    settings = get_settings()
    service.logout(db, raw_refresh=request.cookies.get(settings.refresh_cookie_name))
    db.commit()
    _clear_refresh_cookie(response, settings)


@router.get("/me", response_model=UserProfile)
async def me(user: User = _CURRENT_USER) -> UserProfile:
    return _profile(user)


@router.delete("/me", status_code=204)
async def delete_me(response: Response, db: Session = _DB, user: User = _CURRENT_USER) -> None:
    """Account + data deletion (LGL-007): soft-delete now, hard-delete via the retention job."""
    service.delete_account(db, user)
    db.commit()
    _clear_refresh_cookie(response, get_settings())


@router.post("/verify-email/request", status_code=202, response_model=AuthMessage)
async def request_email_verification(db: Session = _DB, user: User = _CURRENT_USER) -> AuthMessage:
    service.request_email_verification(db, user)
    db.commit()
    return AuthMessage(detail="verification email sent if required")


@router.post("/verify-email/confirm", response_model=UserProfile)
async def confirm_email_verification(body: EmailVerifyConfirm, db: Session = _DB) -> UserProfile:
    user = service.confirm_email_verification(db, raw=body.token)
    db.commit()
    return _profile(user)


@router.post("/password-reset/request", status_code=202, response_model=AuthMessage)
async def request_password_reset(body: PasswordResetRequest, db: Session = _DB) -> AuthMessage:
    service.request_password_reset(db, email=body.email)
    db.commit()
    # Neutral response regardless of whether the account exists (no user enumeration).
    return AuthMessage(detail="if that account exists, a reset email has been sent")


@router.post("/password-reset/confirm", status_code=204)
async def confirm_password_reset(body: PasswordResetConfirm, db: Session = _DB) -> None:
    service.confirm_password_reset(db, raw=body.token, new_password=body.new_password)
    db.commit()
