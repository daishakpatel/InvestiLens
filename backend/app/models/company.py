"""Company reference tables: companies, identifiers, and fiscal calendars (spec §23.1)."""

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UpdatedAtMixin, intpk


class Company(Base, TimestampMixin, UpdatedAtMixin):
    """A public company. `cik` is the stable SEC key; `ticker` can change over time."""

    __tablename__ = "companies"

    id: Mapped[intpk]
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    cik: Mapped[str] = mapped_column(String(10), unique=True)  # zero-padded 10-digit CIK
    name: Mapped[str] = mapped_column(String(512))
    exchange: Mapped[str | None] = mapped_column(String(32))
    sector: Mapped[str | None] = mapped_column(String(128))
    industry: Mapped[str | None] = mapped_column(String(256))
    sic_code: Mapped[str | None] = mapped_column(String(8))
    description: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(512))
    fiscal_year_end: Mapped[str | None] = mapped_column(String(8))  # "MM-DD", e.g. "01-26"
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|delisted|merged


class CompanyIdentifier(Base):
    """Ticker changes, share classes, and name aliases (e.g. "Google" -> Alphabet)."""

    __tablename__ = "company_identifiers"

    id: Mapped[intpk]
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(16))  # ticker|cik|isin|name_alias
    identifier_value: Mapped[str] = mapped_column(String(256))
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    is_primary: Mapped[bool] = mapped_column(default=False)


class FiscalCalendar(Base):
    """Per-company fiscal periods, kept separate from calendar dates (DR-021)."""

    __tablename__ = "fiscal_calendars"
    __table_args__ = (UniqueConstraint("company_id", "fiscal_year", "fiscal_quarter"),)

    id: Mapped[intpk]
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    fiscal_year: Mapped[int] = mapped_column(Integer)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer)  # NULL for full-year rows
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    period_type: Mapped[str] = mapped_column(String(8))  # FY|Q
    weeks_in_period: Mapped[int | None] = mapped_column(Integer)
