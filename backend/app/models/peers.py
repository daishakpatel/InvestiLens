"""Peer sets and valuation history (Phase 7h, FR-PS-001/008, ADR-0046)."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Quantity, intpk


class PeerSet(Base):
    """A company's peers: the deterministic `system_default` (no owner) or a user's own set,
    private to that user. A default with fewer than three members is "insufficient peers"."""

    __tablename__ = "peer_sets"
    __table_args__ = (
        Index("ix_peer_sets_company_id_owner_user_id", "company_id", "owner_user_id"),
    )

    id: Mapped[intpk]
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(16))  # system_default | user
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PeerSetMember(Base):
    __tablename__ = "peer_set_members"
    __table_args__ = (UniqueConstraint("peer_set_id", "peer_company_id"),)

    id: Mapped[intpk]
    peer_set_id: Mapped[int] = mapped_column(ForeignKey("peer_sets.id", ondelete="CASCADE"))
    peer_company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    rationale: Mapped[str] = mapped_column(Text)  # "same SIC 3674; market cap 1.8x target"
    position: Mapped[int] = mapped_column(default=0)  # rule order (nearest market cap first)


class ValuationHistory(Base):
    """One multiple on one date, computed only from what was filed by that date (DR-PS-003).
    `value` is NULL unless `status` is ok; `inputs` names the price, share count and every
    figure's source IDs."""

    __tablename__ = "valuation_history"
    __table_args__ = (UniqueConstraint("company_id", "as_of_date", "multiple"),)

    id: Mapped[intpk]
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    as_of_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(16))  # fiscal_year_end | current
    fiscal_year: Mapped[int | None] = mapped_column()  # for fiscal_year_end rows
    multiple: Mapped[str] = mapped_column(String(32))
    value: Mapped[Quantity | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(16))  # ok | not_meaningful | missing_input | ...
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
