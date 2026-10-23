"""Red flags: reported filing events, detected by rule (Phase 7e, FR-RF-006, ADR-0043)."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, intpk


class RedFlag(Base):
    """One rule firing on one filing under one taxonomy version.

    A new taxonomy version adds rows and leaves the old ones for audit; readers take the newest
    version. `paragraph_id` is NULL when nothing was quoted (a late-filing notice), so the unique
    key treats NULLs as equal. `detected_at` is the first time any version saw this event (alerts
    key off it); `event_date` is the filing's date, never the detection time.
    """

    __tablename__ = "red_flags"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "rule_key",
            "taxonomy_version",
            "filing_id",
            "paragraph_id",
            name="uq_red_flags_event",  # the generated name would pass Postgres's 63 chars
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_red_flags_company_id_event_date", "company_id", "event_date"),
    )

    id: Mapped[intpk]
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    rule_key: Mapped[str] = mapped_column(String(64))
    taxonomy_version: Mapped[str] = mapped_column(String(32))
    filing_id: Mapped[int] = mapped_column(ForeignKey("filings.id", ondelete="CASCADE"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    paragraph_id: Mapped[str | None] = mapped_column(String(64))
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    event_date: Mapped[date | None] = mapped_column(Date)
    severity: Mapped[str] = mapped_column(String(16))  # info | warning | critical
    snippet: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
