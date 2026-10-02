"""Fiscal-calendar persistence (DR-021), idempotent by (company, fiscal_year, fiscal_quarter)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import FiscalCalendar


def get_fiscal_years(session: Session, *, company_id: int) -> list[int]:
    """Distinct full-year fiscal years for a company, ascending (time-range resolution, RAG-003)."""
    return list(
        session.scalars(
            select(FiscalCalendar.fiscal_year)
            .where(
                FiscalCalendar.company_id == company_id,
                FiscalCalendar.period_type == "FY",
            )
            .order_by(FiscalCalendar.fiscal_year)
        )
    )


def upsert_fiscal_period(
    session: Session,
    *,
    company_id: int,
    fiscal_year: int,
    fiscal_quarter: int | None,
    period_start: date,
    period_end: date,
    period_type: str,
    weeks_in_period: int,
) -> None:
    values = dict(
        company_id=company_id,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        period_start=period_start,
        period_end=period_end,
        period_type=period_type,
        weeks_in_period=weeks_in_period,
    )
    stmt = (
        pg_insert(FiscalCalendar)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["company_id", "fiscal_year", "fiscal_quarter"],
            set_={
                "period_start": period_start,
                "period_end": period_end,
                "period_type": period_type,
                "weeks_in_period": weeks_in_period,
            },
        )
    )
    session.execute(stmt)


def clear_company_fiscal_calendars(session: Session, company_id: int) -> None:
    """Remove a company's fiscal-calendar rows so a rebuild is idempotent (NULL quarter safe)."""
    from sqlalchemy import delete

    from app.models import FiscalCalendar as _FC

    session.execute(delete(_FC).where(_FC.company_id == company_id))
