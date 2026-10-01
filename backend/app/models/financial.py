"""Financial data tables (spec §23.1).

`financial_facts` holds raw, point-in-time XBRL facts exactly as reported. `financial_metrics`
holds canonical computed values. They are deliberately separate (spec §11.4, §13.4): facts are
immutable source data, metrics are derived and versioned with citation lineage.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Money, Quantity, TimestampMixin, intpk


class FinancialFact(Base, TimestampMixin):
    """A single raw XBRL fact, point-in-time. Never overwritten; amendments add new rows."""

    __tablename__ = "financial_facts"
    __table_args__ = (
        Index(
            "ix_financial_facts_company_id_concept_tag_period_end",
            "company_id",
            "concept_tag",
            "period_end",
        ),
    )

    id: Mapped[intpk]
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    accession_number: Mapped[str] = mapped_column(String(32))
    # e.g. us-gaap:Revenues. Some XBRL element names are long, hence 256 (see migration 0002).
    concept_tag: Mapped[str] = mapped_column(String(256))
    context_id: Mapped[str | None] = mapped_column(String(128))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    period_type: Mapped[str | None] = mapped_column(String(16))  # duration|instant
    dimensions: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # segment/geography axes
    value: Mapped[Quantity | None] = mapped_column()
    unit: Mapped[str | None] = mapped_column(String(32))
    decimals: Mapped[int | None] = mapped_column(Integer)
    filed_date: Mapped[date | None] = mapped_column(Date)
    is_amended: Mapped[bool] = mapped_column(Boolean, default=False)


class FinancialMetric(Base, TimestampMixin):
    """A canonical computed metric with lineage back to its source (CIT-003).

    `is_derived`/`formula_id`/`source_id`/`as_reported_accession`/`is_latest` support
    point-in-time correctness (§11.4) and restatement handling. `metric_value` uses wider
    precision than money because it also stores ratios.
    """

    __tablename__ = "financial_metrics"
    __table_args__ = (
        UniqueConstraint("company_id", "period", "metric_name", "basis", "as_reported_accession"),
        Index(
            "ix_financial_metrics_company_id_metric_name_is_latest",
            "company_id",
            "metric_name",
            "is_latest",
        ),
    )

    id: Mapped[intpk]
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    period: Mapped[str] = mapped_column(String(32))  # "FY2025", "Q3-FY2026", "TTM-2026Q2"
    fiscal_year: Mapped[int | None] = mapped_column(Integer)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    period_type: Mapped[str] = mapped_column(String(8))  # FY|Q|TTM
    metric_name: Mapped[str] = mapped_column(String(64))
    # Nullable: a sector-inapplicable or uncomputable metric stores NULL + a reason in
    # `quality_flags` (DR-041/042), never a misleading zero. See migration 0003.
    metric_value: Mapped[Quantity | None] = mapped_column()
    unit: Mapped[str] = mapped_column(String(16))  # USD|shares|ratio
    basis: Mapped[str] = mapped_column(String(16), default="gaap")  # gaap|non_gaap
    is_derived: Mapped[bool] = mapped_column(Boolean, default=False)
    source_tag: Mapped[str | None] = mapped_column(String(128))  # XBRL tag chosen
    formula_id: Mapped[str | None] = mapped_column(String(64))
    formula_version: Mapped[str | None] = mapped_column(String(16))
    source_id: Mapped[str | None] = mapped_column(String(128))  # xbrl_fact|derived_metric
    as_reported_accession: Mapped[str | None] = mapped_column(String(32))
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True)
    quality_flags: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class PriceHistory(Base):
    """Daily OHLCV bars. Prices are display money; volume is a raw count (DR-025)."""

    __tablename__ = "price_history"
    __table_args__ = (UniqueConstraint("company_id", "date"),)

    id: Mapped[intpk]
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date)
    open: Mapped[Money | None] = mapped_column()
    high: Mapped[Money | None] = mapped_column()
    low: Mapped[Money | None] = mapped_column()
    close: Mapped[Money | None] = mapped_column()
    adj_close: Mapped[Money | None] = mapped_column()
    volume: Mapped[int | None] = mapped_column(BigInteger)
    provider: Mapped[str | None] = mapped_column(String(32))
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CorporateAction(Base):
    """Splits and dividends used to adjust prices and share counts (DR-025, DR-026)."""

    __tablename__ = "corporate_actions"

    id: Mapped[intpk]
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    action_type: Mapped[str] = mapped_column(String(16))  # split|dividend
    ex_date: Mapped[date | None] = mapped_column(Date)
    ratio_or_amount: Mapped[Quantity | None] = mapped_column()
    provider: Mapped[str | None] = mapped_column(String(32))
