"""Earnings calendar and earnings briefs (Phase 7j, FR-EB-001..014, ADR-0048)."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, intpk


class EarningsEvent(Base):
    """One fiscal quarter's earnings report date, and where the date came from (FR-EB-001/002).

    `source`: `sec_8k` (an Item 2.02 8-K was filed: `status` reported), `announcement` (the
    company stated the date; `quote` holds its words) or `estimated` (last year's date for the
    same quarter, moved 52 weeks so the weekday matches). An estimated date is shown with "~" and
    never notifies on its own. `status` unknown means no date could be found or estimated.
    """

    __tablename__ = "earnings_events"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "fiscal_year", "fiscal_period", name="uq_earnings_events_period"
        ),
        CheckConstraint("status IN ('scheduled', 'reported', 'unknown')", name="status_known"),
        CheckConstraint("source IN ('sec_8k', 'announcement', 'estimated')", name="source_known"),
        CheckConstraint("report_time IN ('bmo', 'amc', 'unknown')", name="report_time_known"),
    )

    id: Mapped[intpk]
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    fiscal_year: Mapped[int] = mapped_column(Integer)
    fiscal_period: Mapped[str] = mapped_column(String(4))  # Q1..Q4
    report_date: Mapped[date | None] = mapped_column(Date)
    report_time: Mapped[str] = mapped_column(String(8), default="unknown")
    source: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    source_id: Mapped[str | None] = mapped_column(String(128))  # filing:<id> or a paragraph ID
    quote: Mapped[str | None] = mapped_column(Text)  # the announcement's own words
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EarningsBrief(Base):
    """A stored pre-earnings preview or post-earnings brief, one row per version (FR-EB-007).

    `inputs_hash` hashes the IDs and values of every input; the same inputs return the stored
    row, changed inputs (a late 10-Q) add version n+1 and keep the old one for audit. `content`
    is the `EarningsPreview` / `EarningsBrief` schema as JSON; `inputs_label` says what changed
    ("after 10-Q filed") for the version switcher.
    """

    __tablename__ = "earnings_briefs"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "fiscal_year",
            "fiscal_period",
            "kind",
            "inputs_hash",
            name="uq_earnings_briefs_inputs",
        ),
        UniqueConstraint(
            "company_id",
            "fiscal_year",
            "fiscal_period",
            "kind",
            "version",
            name="uq_earnings_briefs_version",
        ),
        CheckConstraint("kind IN ('preview', 'brief')", name="kind_known"),
    )

    id: Mapped[intpk]
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    fiscal_year: Mapped[int] = mapped_column(Integer)
    fiscal_period: Mapped[str] = mapped_column(String(4))
    kind: Mapped[str] = mapped_column(String(8))  # preview | brief
    version: Mapped[int] = mapped_column(Integer)
    inputs_hash: Mapped[str] = mapped_column(String(64))
    inputs_label: Mapped[str] = mapped_column(Text)
    report_date_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    prompt_version: Mapped[str] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
