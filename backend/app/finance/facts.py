"""Adapters that build `FactView`s from storage/raw forms (keeps selection logic pure)."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from app.finance.selection import FactView
from app.models import FinancialFact


def fact_view_from_mapping(row: dict[str, Any]) -> FactView:
    """From a `parse_companyfacts` row mapping."""
    return FactView(
        concept_tag=row["concept_tag"],
        period_start=row["period_start"],
        period_end=row["period_end"],
        period_type=row["period_type"],
        value=row["value"],
        unit=row["unit"],
        accession_number=row["accession_number"],
        filed_date=row["filed_date"],
        is_amended=row["is_amended"],
    )


def fact_view_from_orm(fact: FinancialFact) -> FactView:
    return FactView(
        concept_tag=fact.concept_tag,
        period_start=fact.period_start,
        period_end=fact.period_end,
        period_type=fact.period_type or "duration",
        value=Decimal(fact.value) if fact.value is not None else Decimal(0),
        unit=fact.unit or "",
        accession_number=fact.accession_number,
        filed_date=fact.filed_date,
        is_amended=fact.is_amended,
    )


def fact_views(rows: Iterable[dict[str, Any]]) -> list[FactView]:
    return [fact_view_from_mapping(r) for r in rows]
