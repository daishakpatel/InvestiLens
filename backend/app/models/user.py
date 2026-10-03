"""App / user tables (spec §23.2).

Auth follows ADR-0005: passwords are Argon2id hashes, refresh tokens are stored hashed with
rotation/reuse-detection fields. Chat requires a user (ADR-0006: no anonymous AI).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Money, TimestampMixin, intpk


class User(Base, TimestampMixin):
    """A registered user with a monthly AI budget cap (NFR-008)."""

    __tablename__ = "users"

    id: Mapped[intpk]
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))  # Argon2id (AUTH-001)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    role: Mapped[str] = mapped_column(String(16), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Soft-delete marker (LGL-007): set on DELETE /auth/me; a hard-delete job later purges the row.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ai_budget_month_usd: Mapped[Money | None] = mapped_column()


class AuthToken(Base, TimestampMixin):
    """A single-use, hashed email-verification or password-reset token (AUTH-003).

    Only the SHA-256 hash is stored; the raw token is delivered to the user (by email in Phase 5d)
    and never persisted. `used_at` enforces single use; `expires_at` bounds the window.
    """

    __tablename__ = "auth_tokens"

    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(32))  # email_verify|password_reset
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha-256 hex
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshToken(Base):
    """A hashed, rotating refresh token (AUTH-002, ADR-0005).

    `family_id` groups a rotation chain; presenting a `revoked_at` token revokes the family
    (reuse detection). `replaced_by_id` records the rotation successor.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha-256 hex
    family_id: Mapped[str] = mapped_column(String(36), index=True)  # uuid rotation chain
    replaced_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("refresh_tokens.id", ondelete="SET NULL")
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    ip: Mapped[str | None] = mapped_column(String(45))  # IPv6-max length


class Watchlist(Base):
    """A named list of companies owned by a user."""

    __tablename__ = "watchlists"

    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128))


class WatchlistItem(Base):
    """A company on a watchlist."""

    __tablename__ = "watchlist_items"

    id: Mapped[intpk]
    watchlist_id: Mapped[int] = mapped_column(
        ForeignKey("watchlists.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    added_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Alert(Base):
    """A user alert rule (new filing, price move, news category) [P2]."""

    __tablename__ = "alerts"

    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    alert_type: Mapped[str] = mapped_column(String(32))
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    channel: Mapped[str] = mapped_column(String(16), default="in_app")  # email|in_app
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ChatSession(Base, TimestampMixin):
    """A Q&A session about one company. Requires a user (ADR-0006)."""

    __tablename__ = "chat_sessions"

    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))


class ChatMessage(Base, TimestampMixin):
    """One turn in a chat session, with citation and cost/latency accounting."""

    __tablename__ = "chat_messages"

    id: Mapped[intpk]
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user|assistant
    content: Mapped[str] = mapped_column(Text)
    source_ids: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    tool_trace: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    cost_usd: Mapped[Money | None] = mapped_column()
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    feedback: Mapped[str | None] = mapped_column(String(8))  # up|down|null
    feedback_reason: Mapped[str | None] = mapped_column(Text)


class ReportFeedback(Base, TimestampMixin):
    """User feedback on a report or a specific claim."""

    __tablename__ = "report_feedback"

    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("research_reports.id", ondelete="CASCADE"), index=True
    )
    claim_id: Mapped[str | None] = mapped_column(String(64))
    rating: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text)
