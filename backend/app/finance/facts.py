"""Adapters that build `FactView`s from storage/raw forms (keeps selection logic pure)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
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
        fact_id=fact.id,
    )


def fact_views(rows: Iterable[dict[str, Any]]) -> list[FactView]:
    return [fact_view_from_mapping(r) for r in rows]


def with_composites(
    facts: Sequence[FactView], composites: Mapping[str, Sequence[str]]
) -> list[FactView]:
    """`facts` plus one synthetic fact per composite tag for every period a filing reports all
    of its components: their sum (Phase 7h, ADR-0046). A filer that stopped tagging a total
    (AMD's and Intel's depreciation & amortization) keeps its parts, and selection treats the
    composite like any other tag, so annual, quarterly and point-in-time paths all see it."""
    out = list(facts)
    for tag, components in composites.items():
        groups: dict[tuple[Any, ...], dict[str, FactView]] = {}
        for fact in facts:
            if fact.concept_tag in components:
                key = (fact.period_start, fact.period_end, fact.period_type, fact.accession_number)
                groups.setdefault(key, {}).setdefault(fact.concept_tag, fact)
        for parts in groups.values():
            if len(parts) != len(components):
                continue  # a component missing for this period: no total, never a partial sum
            first = parts[components[0]]
            out.append(
                FactView(
                    concept_tag=tag,
                    period_start=first.period_start,
                    period_end=first.period_end,
                    period_type=first.period_type,
                    value=sum((parts[c].value for c in components), Decimal(0)),
                    unit=first.unit,
                    accession_number=first.accession_number,
                    filed_date=max(
                        (p.filed_date for p in parts.values() if p.filed_date), default=None
                    ),
                    is_amended=any(p.is_amended for p in parts.values()),
                    component_ids=tuple(p.fact_id for p in parts.values() if p.fact_id is not None),
                )
            )
    return out
