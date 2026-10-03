"""Auth request/response schemas (spec §24.2, §26.1). Logic itself is Phase 4b."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, description="Argon2id-hashed server-side (AUTH-001)")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Access token in the body; the refresh token is set as an httpOnly cookie (AUTH-002)."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105  (OAuth token *type*, not a secret)
    expires_in: int = 900  # 15 minutes (AUTH-002)


class UserProfile(BaseModel):
    id: str
    email: EmailStr
    role: str
    email_verified: bool = False


class EmailVerifyConfirm(BaseModel):
    token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=12, description="Argon2id-hashed server-side (AUTH-001)")


class AuthMessage(BaseModel):
    """A neutral acknowledgement (used where revealing specifics would enable enumeration)."""

    detail: str
