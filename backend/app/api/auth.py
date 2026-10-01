"""Auth endpoints (spec §24.2, §26.1). Handler logic itself is Phase 4b.

Shapes are final now so the frontend can build the auth flow against the contract.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.errors import not_implemented
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserProfile

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", status_code=201, response_model=UserProfile)
async def register(body: RegisterRequest) -> UserProfile:
    raise not_implemented("Auth lands in Phase 4b")


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    raise not_implemented("Auth lands in Phase 4b")


@router.post("/refresh", response_model=TokenResponse)
async def refresh() -> TokenResponse:
    raise not_implemented("Auth lands in Phase 4b")


@router.post("/logout", status_code=204)
async def logout() -> None:
    raise not_implemented("Auth lands in Phase 4b")


@router.get("/me", response_model=UserProfile)
async def me() -> UserProfile:
    raise not_implemented("Auth lands in Phase 4b")


@router.delete("/me", status_code=204)
async def delete_me() -> None:
    """Account + data deletion (LGL-007)."""
    raise not_implemented("Auth lands in Phase 4b")
