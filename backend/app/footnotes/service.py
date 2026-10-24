"""Read side of the footnotes feature (Phase 7f, FR-FN-010/011): notes, facts and note scopes.

Notes come from `documents.metadata['notes']` (written at parse time), summaries from the cache
beside them, facts from the FY rows `footnote_builder` wrote. Nothing here calls a model.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.finance.concept_map import load_concept_map
from app.finance.display import metric_label
from app.finance.footnote_builder import FOOTNOTE_DERIVED
from app.footnotes.summary import SUMMARISED_CATEGORIES, cached_summary, model_label
from app.ingestion.documents.notes import NOTE_TAXONOMY_VERSION
from app.models import Company, Document, FinancialMetric, MetricGap
from app.schemas.footnotes import (
    FootnoteCategory,
    FootnoteFact,
    FootnoteFactsResponse,
    FootnoteGap,
    NoteItem,
    NoteSummaryView,
)

# Categories with XBRL facts, in page order; existing FY rows shown with them.
FACT_CATEGORIES = ("debt", "leases", "income_taxes", "commitments_contingencies", "stock_comp")
_EXISTING = {"debt": ("total_debt",), "stock_comp": ("stock_based_compensation",)}
_DERIVED_CATEGORY = {"debt_due_within_2y_share": "debt", "lease_adjusted_debt": "leases"}


def stored_notes(document: Document | None) -> dict[str, Any]:
    """The document's segmentation; an unsegmented one reads as low confidence with no notes."""
    stored = (document.doc_metadata or {}).get("notes") if document else None
    return stored or {"taxonomy": NOTE_TAXONOMY_VERSION, "low_confidence": True, "items": []}


def category_scope(document: Document | None, category: str) -> list[str]:
    """Paragraph IDs of every note of `category` in the document (a filer may split one)."""
    return [
        pid
        for note in stored_notes(document)["items"]
        if note["category"] == category
        for pid in note["paragraph_ids"]
    ]


def note_items(document: Document) -> list[NoteItem]:
    model = model_label(get_settings())
    items = []
    for note in stored_notes(document)["items"]:
        view = None
        if note["category"] in SUMMARISED_CATEGORIES:
            summary = cached_summary(document, note["note_id"], model)
            if summary is None:
                view = NoteSummaryView(status="pending")
            else:
                view = NoteSummaryView(
                    status="abstained" if summary.abstain else "summarised",
                    bullets=summary.bullets,
                    model=summary.model,
                )
        items.append(NoteItem(**note, summary=view))
    return items


def _fact(row: FinancialMetric) -> FootnoteFact:
    flags = row.quality_flags or {}
    return FootnoteFact(
        metric=row.metric_name,
        label=metric_label(row.metric_name),
        value=row.metric_value,
        unit=row.unit or "",
        period=row.period,
        source_id=row.source_id or "",
        is_derived=row.is_derived,
        formula=flags.get("derived"),
        from_inline_xbrl=flags.get("source") == "inline_xbrl",
    )


def footnote_facts(session: Session, company: Company) -> FootnoteFactsResponse:
    """The latest fiscal year's footnote facts and gaps, grouped by note category."""
    cmap = load_concept_map(ticker=company.ticker, cik=company.cik, sector=company.sector)
    by_category: dict[str, list[str]] = {c: list(_EXISTING.get(c, ())) for c in FACT_CATEGORIES}
    for metric, category in cmap.footnote_metrics.items():
        by_category.setdefault(category, []).append(metric)
    for metric, category in _DERIVED_CATEGORY.items():
        by_category[category].append(metric)
    own = [*cmap.footnote_metrics, *FOOTNOTE_DERIVED]
    latest = session.scalar(
        select(FinancialMetric.fiscal_year)
        .where(
            FinancialMetric.company_id == company.id,
            FinancialMetric.period_type == "FY",
            FinancialMetric.metric_name.in_(own),
        )
        .order_by(FinancialMetric.fiscal_year.desc())
        .limit(1)
    )
    if latest is None:
        return FootnoteFactsResponse(company_ticker=company.ticker, fiscal_year=None, categories=[])
    names = [m for metrics in by_category.values() for m in metrics]
    rows = {
        row.metric_name: row
        for row in session.scalars(
            select(FinancialMetric).where(
                FinancialMetric.company_id == company.id,
                FinancialMetric.period_type == "FY",
                FinancialMetric.fiscal_year == latest,
                FinancialMetric.is_latest.is_(True),
                FinancialMetric.metric_name.in_(names),
            )
        )
    }
    gaps = {
        gap.metric: gap
        for gap in session.scalars(
            select(MetricGap).where(
                MetricGap.company_id == company.id,
                MetricGap.period_label == f"FY{latest}",
                MetricGap.metric.in_(own),
            )
        )
    }
    categories = [
        FootnoteCategory(
            category=category,
            facts=[_fact(rows[m]) for m in metrics if m in rows],
            gaps=[
                FootnoteGap(
                    metric=m,
                    label=metric_label(m),
                    period=gaps[m].period_label,
                    reason=gaps[m].reason,
                )
                for m in metrics
                if m in gaps and m not in rows
            ],
        )
        for category, metrics in by_category.items()
    ]
    return FootnoteFactsResponse(
        company_ticker=company.ticker, fiscal_year=latest, categories=categories
    )
