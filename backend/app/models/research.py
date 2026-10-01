"""AI output tables: reports, their sources, and claim verifications (spec §23.1).

Reproducibility (NFR-010): every report records `model`, `prompt_version`, and `data_version`.
Every displayed claim traces to a `research_sources` row (CIT-001) and is gated by a
`claim_verifications` row (CIT-005).
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


class ResearchReport(Base):
    """A generated research report. `user_id` is nullable (system-generated for seed companies)."""

    __tablename__ = "research_reports"

    id: Mapped[intpk]
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    model: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    report_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    data_version: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    cost_usd: Mapped[Money | None] = mapped_column()
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    supersedes_report_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_reports.id", ondelete="SET NULL")
    )


class ResearchSource(Base):
    """A backend-issued source cited by a report (CIT-001, ADR-0004 anchor fields)."""

    __tablename__ = "research_sources"

    id: Mapped[intpk]
    report_id: Mapped[int] = mapped_column(
        ForeignKey("research_reports.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[str] = mapped_column(String(128))
    source_type: Mapped[str | None] = mapped_column(String(32))
    citation_text: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    page: Mapped[int | None] = mapped_column(Integer)  # PDFs only (§13.3)
    section_path: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)
    tier: Mapped[int | None] = mapped_column(Integer)


class ClaimVerification(Base, TimestampMixin):
    """Per-claim verification outcome. Attaches to a report or a chat message (CIT-005)."""

    __tablename__ = "claim_verifications"

    id: Mapped[intpk]
    report_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_reports.id", ondelete="CASCADE"), index=True
    )
    chat_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="CASCADE"), index=True
    )
    claim_id: Mapped[str | None] = mapped_column(String(64))
    claim_text: Mapped[str | None] = mapped_column(Text)
    source_ids: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    status: Mapped[str | None] = mapped_column(String(16))  # accepted|rejected|softened
    reason_code: Mapped[str | None] = mapped_column(String(64))
    entailment_label: Mapped[str | None] = mapped_column(String(32))
    numeric_match: Mapped[bool | None] = mapped_column(Boolean)
