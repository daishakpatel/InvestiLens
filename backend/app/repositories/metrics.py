"""Canonical financial_metrics persistence (Phase 1b).

Idempotent by the natural key (company, period, metric, basis, as_reported_accession). Restated
values keep both rows with `is_latest` distinguishing them (DR-023).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import FinancialMetric


def clear_company_metrics(session: Session, company_id: int) -> None:
    """Remove a company's metrics so a rebuild is idempotent."""
    session.execute(delete(FinancialMetric).where(FinancialMetric.company_id == company_id))


def upsert_metric(
    session: Session,
    *,
    company_id: int,
    period: str,
    fiscal_year: int | None,
    fiscal_quarter: int | None,
    period_start: date | None,
    period_end: date | None,
    period_type: str,
    metric_name: str,
    metric_value: Decimal | None,
    unit: str,
    basis: str = "gaap",
    is_derived: bool = False,
    source_tag: str | None = None,
    formula_id: str | None = None,
    source_id: str | None = None,
    as_reported_accession: str | None = None,
    is_latest: bool = True,
    quality_flags: dict[str, Any] | None = None,
) -> None:
    """Insert or update one canonical metric row (ING-001 idempotent)."""
    values = dict(
        company_id=company_id,
        period=period,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        period_start=period_start,
        period_end=period_end,
        period_type=period_type,
        metric_name=metric_name,
        metric_value=metric_value,
        unit=unit,
        basis=basis,
        is_derived=is_derived,
        source_tag=source_tag,
        formula_id=formula_id,
        source_id=source_id,
        as_reported_accession=as_reported_accession,
        is_latest=is_latest,
        quality_flags=quality_flags,
    )
    update_cols = {
        k: values[k]
        for k in (
            "metric_value",
            "unit",
            "is_derived",
            "source_tag",
            "formula_id",
            "source_id",
            "is_latest",
            "quality_flags",
            "fiscal_year",
            "fiscal_quarter",
            "period_start",
            "period_end",
            "period_type",
        )
    }
    stmt = (
        pg_insert(FinancialMetric)
        .values(**values)
        .on_conflict_do_update(
            index_elements=[
                "company_id",
                "period",
                "metric_name",
                "basis",
                "as_reported_accession",
            ],
            set_=update_cols,
        )
    )
    session.execute(stmt)
