"""Investment thesis tracker (Phase 7k, FR-TH-001..014, SEC-TH-001..003, ADR-0049).

Every row belongs to one user through `theses.user_id`; deleting a thesis, or the user, removes
its KPIs, events and revisions (FK cascade). Thesis text is the user's private data: it is never
logged (SEC-TH-002).
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
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

from app.models.base import Base, Quantity, TimestampMixin, UpdatedAtMixin, intpk


class Thesis(Base, TimestampMixin, UpdatedAtMixin):
    """A user's written thesis on one company. `stance` is the user's own tag, not advice."""

    __tablename__ = "theses"
    __table_args__ = (
        Index("ix_theses_user_id_status", "user_id", "status"),
        Index("ix_theses_company_id", "company_id"),
        CheckConstraint("stance IN ('long', 'short', 'watch', 'avoid')", name="stance_known"),
        CheckConstraint("status IN ('active', 'closed')", name="status_known"),
    )

    id: Mapped[intpk]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    body_md: Mapped[str] = mapped_column(Text)
    stance: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(8), default="active")


class ThesisKpi(Base, TimestampMixin):
    """A measurable claim: `metric` (from the registry) `comparator` `threshold`, in the metric's
    canonical unit. The current `state` and the value it rests on are kept here; history lives in
    `thesis_events` (transitions only)."""

    __tablename__ = "thesis_kpis"
    __table_args__ = (
        Index("ix_thesis_kpis_thesis_id", "thesis_id"),
        CheckConstraint("comparator IN ('gte', 'lte', 'gt', 'lt')", name="comparator_known"),
        CheckConstraint("state IN ('met', 'broken', 'no_data')", name="state_known"),
    )

    id: Mapped[intpk]
    thesis_id: Mapped[int] = mapped_column(ForeignKey("theses.id", ondelete="CASCADE"))
    metric: Mapped[str] = mapped_column(String(64))
    period_type: Mapped[str] = mapped_column(String(8))  # FY | Q | TTM | LATEST
    comparator: Mapped[str] = mapped_column(String(4))
    threshold: Mapped[Quantity] = mapped_column()
    unit: Mapped[str] = mapped_column(String(16))
    label: Mapped[str] = mapped_column(String(120))
    rationale: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(8), default="no_data")
    last_value: Mapped[Quantity | None] = mapped_column()
    last_source_ids: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    last_period: Mapped[str | None] = mapped_column(String(32))
    last_period_end: Mapped[date | None] = mapped_column(Date)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ThesisEvent(Base):
    """Append-only timeline: `kpi_met`, `kpi_broken`, `red_flag`, `brief_published`,
    `user_note`, `status_changed`. A red flag or brief is linked once per thesis
    (`uq_thesis_events_link`); they are informational and never change a KPI's state."""

    __tablename__ = "thesis_events"
    __table_args__ = (
        Index("ix_thesis_events_thesis_id_occurred_at", "thesis_id", "occurred_at"),
        Index(
            "uq_thesis_events_link",
            "thesis_id",
            "kind",
            "ref_id",
            unique=True,
            postgresql_where=text("kind IN ('red_flag', 'brief_published')"),
        ),
        CheckConstraint(
            "kind IN ('kpi_met', 'kpi_broken', 'red_flag', 'brief_published', 'user_note', "
            "'status_changed')",
            name="kind_known",
        ),
    )

    id: Mapped[intpk]
    thesis_id: Mapped[int] = mapped_column(ForeignKey("theses.id", ondelete="CASCADE"))
    kpi_id: Mapped[int | None] = mapped_column(ForeignKey("thesis_kpis.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(24))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ref_type: Mapped[str | None] = mapped_column(String(24))  # metric | red_flag | earnings_brief
    ref_id: Mapped[str | None] = mapped_column(String(160))  # a backend source ID or row id
    note: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )


class ThesisRevision(Base):
    """Every saved body, numbered from 1; an edit adds a revision, never overwrites one."""

    __tablename__ = "thesis_revisions"

    thesis_id: Mapped[int] = mapped_column(
        ForeignKey("theses.id", ondelete="CASCADE"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    body_md: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
