"""Company guidance and how it turned out (Phase 7i, FR-GD-001..006, ADR-0047)."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Quantity, intpk


class GuidanceItem(Base):
    """One number a company guided to, quoted from its own earnings release.

    `verified` rows passed every deterministic check and are the only ones shown; `rejected` rows
    keep what the model said and why it failed, for audit (FR-GD-004). Exactly one of `point` or
    (`low`, `high`) is set on a verified row; `derived_range` marks a range computed in code from
    "X, plus or minus Y" wording. `superseded_by` points at the next release's guidance for the
    same period, metric and basis (FR-GD-009).
    """

    __tablename__ = "guidance_items"
    __table_args__ = (
        Index("ix_guidance_items_company_id_fiscal_year", "company_id", "fiscal_year"),
        Index("ix_guidance_items_source_document_id", "source_document_id"),
        # FR-GD-001: a verified row states a single value or a full range, never both.
        CheckConstraint(
            "confidence_state <> 'verified' OR "
            "((point IS NOT NULL) <> (low IS NOT NULL AND high IS NOT NULL))",
            name="one_value_form",
        ),
    )

    id: Mapped[intpk]
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    source_document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    paragraph_id: Mapped[str | None] = mapped_column(String(64))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fiscal_year: Mapped[int | None] = mapped_column(Integer)
    fiscal_period: Mapped[str | None] = mapped_column(String(4))  # Q1..Q4 | FY
    metric: Mapped[str] = mapped_column(String(32))
    low: Mapped[Quantity | None] = mapped_column()
    high: Mapped[Quantity | None] = mapped_column()
    point: Mapped[Quantity | None] = mapped_column()
    unit: Mapped[str | None] = mapped_column(String(24))  # usd | ratio | percent_of_revenue
    basis: Mapped[str | None] = mapped_column(String(16))  # gaap | non_gaap | unspecified
    derived_range: Mapped[bool] = mapped_column(Boolean, default=False)
    quote: Mapped[str] = mapped_column(Text)
    period_text: Mapped[str | None] = mapped_column(Text)
    confidence_state: Mapped[str] = mapped_column(String(16))  # verified | rejected
    rejection_reason: Mapped[str | None] = mapped_column(String(64))
    superseded_by: Mapped[int | None] = mapped_column(
        ForeignKey("guidance_items.id", ondelete="SET NULL")
    )
    taxonomy_version: Mapped[str] = mapped_column(String(32))
    prompt_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GuidanceOutcome(Base):
    """A verified guidance item against the reported actual (FR-GD-007/008).

    `actual_value` is NULL with `result` `actual_unavailable` or `not_comparable` and a
    `reason_code`, never zero. Deltas are actual minus the bound (money in raw USD, ratios in
    ratio points); `delta_vs_mid_pct` is the delta over the midpoint, for display.
    `computed_at` only moves when the result or actual changes, so an alert fires once.
    """

    __tablename__ = "guidance_outcomes"
    __table_args__ = (
        CheckConstraint(
            "result IN ('above_range', 'within_range', 'below_range', 'not_comparable', "
            "'actual_unavailable')",
            name="result_known",
        ),
    )

    guidance_id: Mapped[int] = mapped_column(
        ForeignKey("guidance_items.id", ondelete="CASCADE"), primary_key=True
    )
    actual_value: Mapped[Quantity | None] = mapped_column()
    actual_source_ids: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    delta_vs_low: Mapped[Quantity | None] = mapped_column()
    delta_vs_high: Mapped[Quantity | None] = mapped_column()
    delta_vs_mid: Mapped[Quantity | None] = mapped_column()
    delta_vs_mid_pct: Mapped[Quantity | None] = mapped_column()
    # above_range | within_range | below_range | not_comparable | actual_unavailable
    result: Mapped[str] = mapped_column(String(24))
    reason_code: Mapped[str | None] = mapped_column(String(32))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
