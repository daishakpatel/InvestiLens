"""Guidance persistence and reads (Phase 7i, FR-GD-001..014, ADR-0047)."""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import case, delete, exists, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, aliased

from app.models import (
    Company,
    Document,
    FinancialMetric,
    FiscalCalendar,
    GuidanceItem,
    GuidanceOutcome,
)

Period = tuple[int, str]  # (fiscal_year, "Q1".."Q4" | "FY")


def earnings_releases(
    session: Session, company_id: int, *, exhibit_types: Collection[str], parser_version: str
) -> list[Document]:
    """The company's parsed press releases of these exhibit types, newest first."""
    return list(
        session.scalars(
            select(Document)
            .where(
                Document.company_id == company_id,
                Document.document_type == "earnings_release",
                Document.parser_version == parser_version,
                Document.doc_metadata["exhibit_type"].astext.in_(exhibit_types),
            )
            .order_by(Document.published_at.desc().nulls_last(), Document.id.desc())
        )
    )


def fiscal_calendar(session: Session, company_id: int) -> list[FiscalCalendar]:
    return list(
        session.scalars(select(FiscalCalendar).where(FiscalCalendar.company_id == company_id))
    )


def replace_document_items(
    session: Session, document_id: int, rows: Sequence[dict[str, Any]]
) -> None:
    """A document's items, all of them replaced (a new prompt version re-extracts it)."""
    session.execute(delete(GuidanceItem).where(GuidanceItem.source_document_id == document_id))
    if rows:
        session.execute(insert(GuidanceItem).values(list(rows)))


def verified_items(session: Session, company_id: int) -> list[GuidanceItem]:
    return list(
        session.scalars(
            select(GuidanceItem)
            .where(
                GuidanceItem.company_id == company_id,
                GuidanceItem.confidence_state == "verified",
            )
            .order_by(GuidanceItem.issued_at, GuidanceItem.id)
        )
    )


def set_superseded(session: Session, chain: Mapping[int, int | None]) -> None:
    for item_id, next_id in chain.items():
        session.execute(
            update(GuidanceItem)
            .where(GuidanceItem.id == item_id, GuidanceItem.superseded_by.is_distinct_from(next_id))
            .values(superseded_by=next_id)
        )


def actual_rows(
    session: Session, company_id: int, periods: Iterable[Period], names: Collection[str]
) -> dict[Period, dict[str, tuple[Decimal, str]]]:
    """Latest GAAP rows per period: {(fy, "Q3"): {metric_name: (value, source_id)}}."""
    wanted = set(periods)
    if not wanted:
        return {}
    rows = session.execute(
        select(
            FinancialMetric.fiscal_year,
            FinancialMetric.fiscal_quarter,
            FinancialMetric.period_type,
            FinancialMetric.metric_name,
            FinancialMetric.metric_value,
            FinancialMetric.source_id,
        ).where(
            FinancialMetric.company_id == company_id,
            FinancialMetric.period_type.in_(("Q", "FY")),
            FinancialMetric.is_latest.is_(True),
            FinancialMetric.basis == "gaap",
            FinancialMetric.metric_name.in_(names),
            FinancialMetric.fiscal_year.in_({fy for fy, _ in wanted}),
            FinancialMetric.metric_value.is_not(None),
        )
    )
    found: dict[Period, dict[str, tuple[Decimal, str]]] = {}
    for fy, fq, kind, name, value, source in rows:
        period = (fy, "FY" if kind == "FY" else f"Q{fq}")
        if period in wanted and source and value is not None:
            found.setdefault(period, {})[name] = (value, source)
    return found


def upsert_outcomes(session: Session, rows: Sequence[dict[str, Any]]) -> None:
    """Store outcomes; `computed_at` moves only when the result or the actual changed, so the
    alert for an outcome fires once (FR-GD-013)."""
    if not rows:
        return
    stmt = insert(GuidanceOutcome).values(list(rows))
    current = GuidanceOutcome.__table__.c
    changed = (current.result.is_distinct_from(stmt.excluded.result)) | (
        current.actual_value.is_distinct_from(stmt.excluded.actual_value)
    )
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=[GuidanceOutcome.guidance_id],
            set_={
                **{
                    name: stmt.excluded[name]
                    for name in rows[0]
                    if name not in ("guidance_id", "computed_at")
                },
                "computed_at": case(
                    (changed, stmt.excluded.computed_at), else_=current.computed_at
                ),
            },
        )
    )


def items_with_outcomes(
    session: Session, company_id: int, *, fiscal_year: int | None = None
) -> list[tuple[GuidanceItem, GuidanceOutcome | None, Document]]:
    """Verified items with their outcome and release, by period then issue date."""
    query = (
        select(GuidanceItem, GuidanceOutcome, Document)
        .join(Document, Document.id == GuidanceItem.source_document_id)
        .outerjoin(GuidanceOutcome, GuidanceOutcome.guidance_id == GuidanceItem.id)
        .where(
            GuidanceItem.company_id == company_id,
            GuidanceItem.confidence_state == "verified",
        )
        .order_by(
            GuidanceItem.fiscal_year.desc(),
            GuidanceItem.fiscal_period.desc(),
            GuidanceItem.metric,
            GuidanceItem.issued_at,
            GuidanceItem.id,
        )
    )
    if fiscal_year is not None:
        query = query.where(GuidanceItem.fiscal_year == fiscal_year)
    return [(i, o, d) for i, o, d in session.execute(query)]


def fiscal_years(session: Session, company_id: int) -> list[int]:
    return [
        y
        for y in session.scalars(
            select(GuidanceItem.fiscal_year)
            .where(
                GuidanceItem.company_id == company_id,
                GuidanceItem.confidence_state == "verified",
                GuidanceItem.fiscal_year.is_not(None),
            )
            .distinct()
            .order_by(GuidanceItem.fiscal_year.desc())
        )
        if y is not None
    ]


def _is_headline() -> Any:
    """No earlier item points at this one: it is the first guidance for its key."""
    earlier = aliased(GuidanceItem)
    return ~exists().where(earlier.superseded_by == GuidanceItem.id)


def headline_outcomes(
    session: Session,
    *,
    company_ids: Collection[int],
    metrics: Collection[str],
    results: Collection[str],
    computed_after: datetime,
    computed_until: datetime,
    issued_since: date | None = None,
) -> list[tuple[GuidanceItem, GuidanceOutcome, str]]:
    """Headline (initial-guidance) outcomes computed in the window, with the ticker."""
    query = (
        select(GuidanceItem, GuidanceOutcome, Company.ticker)
        .join(GuidanceOutcome, GuidanceOutcome.guidance_id == GuidanceItem.id)
        .join(Company, Company.id == GuidanceItem.company_id)
        .where(
            GuidanceItem.company_id.in_(company_ids),
            GuidanceItem.confidence_state == "verified",
            GuidanceItem.metric.in_(metrics),
            GuidanceOutcome.result.in_(results),
            GuidanceOutcome.computed_at > computed_after,
            GuidanceOutcome.computed_at <= computed_until,
            _is_headline(),
        )
        .order_by(GuidanceOutcome.computed_at, GuidanceItem.id)
    )
    if issued_since is not None:
        query = query.where(GuidanceItem.issued_at >= issued_since)
    return [(i, o, t) for i, o, t in session.execute(query)]
