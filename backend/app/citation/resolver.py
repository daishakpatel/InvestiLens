"""Resolve a backend-issued source_id to its full record for the citation modal (CIT-006, §13.3).

Powers `GET /sources/{source_id}` for all six source types. The id scheme (prefix-based, with the
document-chunk anchor as the default) keeps resolution unambiguous:
- ``news:<id>``     → news_item
- ``xbrl:<fact_id>``→ xbrl_fact
- ``derived:…`` (or a `financial_metrics.source_id` match) → derived_metric (with lineage, CIT-003)
- otherwise the id is a chunk ``paragraph_id`` → text_chunk / table_chunk, or earnings_release /
  transcript when the parent document is one.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk, FinancialFact, FinancialMetric, News
from app.schemas.citations import SourceDetail
from app.schemas.sources import (
    DerivedMetricSource,
    EarningsReleaseSource,
    NewsItemSource,
    TableChunkSource,
    TextChunkSource,
    XbrlFactSource,
)


def _news(row: News) -> SourceDetail:
    source = NewsItemSource(
        source_id=f"news:{row.id}",
        tier=4,
        url=row.url,
        news_id=str(row.id),
        publisher=row.publisher,
        published_at=row.published_at.isoformat() if row.published_at else None,
        excerpt_span=row.description,
    )
    text = " ".join(p for p in (row.title, row.description) if p)
    return SourceDetail(source=source, text=text, deep_link=row.url)


def _xbrl(row: FinancialFact) -> SourceDetail:
    source = XbrlFactSource(
        source_id=f"xbrl:{row.id}",
        tier=1,
        accession_number=row.accession_number,
        concept_tag=row.concept_tag,
        context_id=row.context_id,
        unit=row.unit,
        value=row.value,
    )
    return SourceDetail(
        source=source, text=f"{row.concept_tag} = {row.value} {row.unit or ''}".strip()
    )


def _derived(row: FinancialMetric) -> SourceDetail:
    flags = row.quality_flags or {}
    inputs = [dict(i) for i in flags.get("inputs", [])]
    source = DerivedMetricSource(
        source_id=row.source_id or f"derived:{row.formula_id}:{row.period}",
        tier=1,
        formula_id=row.formula_id or row.metric_name,
        formula_version=str(flags.get("formula_version") or ""),
        input_source_ids=[str(i.get("source_id")) for i in inputs if i.get("source_id")],
        value=row.metric_value,
        period=row.period,
    )
    return SourceDetail(
        source=source,
        text=f"{row.metric_name} {row.period} = {row.metric_value} {row.unit}".strip(),
        lineage=[{k: str(v) for k, v in i.items()} for i in inputs],
    )


def _chunk(session: Session, row: DocumentChunk) -> SourceDetail:
    doc = session.get(Document, row.document_id)
    deep_link = doc.source_url if doc else None
    anchor = row.paragraph_id or f"{row.document_id}_{row.chunk_index}"
    section_path = list(row.section_path or [])
    if doc and doc.document_type in {"earnings_release", "transcript"}:
        source: EarningsReleaseSource | TextChunkSource | TableChunkSource = EarningsReleaseSource(
            source_id=anchor,
            tier=2 if doc.document_type == "earnings_release" else 3,
            source_type=doc.document_type,  # type: ignore[arg-type]
            document_id=str(row.document_id),
            paragraph_id=row.paragraph_id,
            char_start=row.char_start,
            char_end=row.char_end,
        )
    elif row.chunk_type == "table":
        meta = row.chunk_metadata or {}
        source = TableChunkSource(
            source_id=anchor,
            tier=row.tier or 1,
            document_id=str(row.document_id),
            table_id=str(meta.get("table_id", anchor)),
            row_labels=list(meta.get("row_labels", []) or []),
            col_labels=list(meta.get("col_labels", []) or []),
            cell_refs=list(meta.get("cell_refs", []) or []),
        )
    else:
        source = TextChunkSource(
            source_id=anchor,
            tier=row.tier or 1,
            document_id=str(row.document_id),
            section_path=section_path,
            paragraph_id=row.paragraph_id,
            char_start=row.char_start,
            char_end=row.char_end,
            page=row.page,
            text=row.text,
        )
    return SourceDetail(
        source=source,
        text=row.text,
        highlight_start=row.char_start,
        highlight_end=row.char_end,
        deep_link=deep_link,
    )


def resolve_source(session: Session, source_id: str) -> SourceDetail | None:
    """Resolve a source_id to its full record + marked span + deep link, or None if unknown."""
    if source_id.startswith("news:"):
        row = session.get(News, _as_int(source_id.split(":", 1)[1]))
        return _news(row) if row else None
    if source_id.startswith("xbrl:"):
        fact = session.get(FinancialFact, _as_int(source_id.split(":", 1)[1]))
        return _xbrl(fact) if fact else None
    metric = session.scalar(
        select(FinancialMetric).where(
            FinancialMetric.source_id == source_id, FinancialMetric.is_derived.is_(True)
        )
    )
    if metric is not None:
        return _derived(metric)
    chunk = session.scalar(select(DocumentChunk).where(DocumentChunk.paragraph_id == source_id))
    return _chunk(session, chunk) if chunk else None


def _as_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return -1
