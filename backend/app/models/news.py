"""News and ownership tables (spec §23.1).

Only headline-level news fields are stored by default; full `content` only where the
provider's license permits (LGL-004, ADR-0008).
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Money, Quantity, TimestampMixin, intpk


class News(Base, TimestampMixin):
    """A news item. `document_id` links the unified registry; nullable for headline-only rows."""

    __tablename__ = "news"

    id: Mapped[intpk]
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(String(256))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    content: Mapped[str | None] = mapped_column(Text)  # only if licensed (LGL-004)
    category: Mapped[str | None] = mapped_column(String(64))
    relevance_score: Mapped[Quantity | None] = mapped_column()
    event_cluster_id: Mapped[str | None] = mapped_column(String(64))
    content_hash: Mapped[str | None] = mapped_column(String(64))


class InsiderTransaction(Base):
    """Form 4 insider transactions (P2)."""

    __tablename__ = "insider_transactions"

    id: Mapped[intpk]
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    accession_number: Mapped[str | None] = mapped_column(String(32))
    insider_name: Mapped[str | None] = mapped_column(String(256))
    role: Mapped[str | None] = mapped_column(String(128))
    transaction_date: Mapped[date | None] = mapped_column(Date)
    code: Mapped[str | None] = mapped_column(String(8))  # SEC transaction code
    shares: Mapped[int | None] = mapped_column(BigInteger)
    price: Mapped[Money | None] = mapped_column()
    is_10b5_1: Mapped[bool | None] = mapped_column(Boolean)
    post_holdings: Mapped[int | None] = mapped_column(BigInteger)


class InstitutionalHolding(Base):
    """13F institutional holdings (P2)."""

    __tablename__ = "institutional_holdings"

    id: Mapped[intpk]
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    filer_cik: Mapped[str | None] = mapped_column(String(10))
    filer_name: Mapped[str | None] = mapped_column(String(256))
    period_end: Mapped[date | None] = mapped_column(Date)
    shares: Mapped[int | None] = mapped_column(BigInteger)
    value: Mapped[Money | None] = mapped_column()
    change_shares: Mapped[int | None] = mapped_column(BigInteger)
