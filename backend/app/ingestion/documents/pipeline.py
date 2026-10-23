"""Document parse & chunk pipeline (Phase 2a; Phase 7c, ADR-0041).

Reads a document's raw HTML (from object storage), cleans it, detects sections, chunks it
(section-aware, tables as first-class chunks), and persists `document_chunks`. Records an
ingestion run and flags low-confidence section parses into `data_quality_issues`. `embedding`
stays NULL (Phase 2b) except where unchanged text keeps its vector. Idempotent (DP-006).

A parsed document is stamped with `PARSER_VERSION`, so `parse_company_documents` skips documents
that are already current (FR-EX-014). A late-filing notice gets metadata only: no chunks and no
embedding spend on a two-page form. An 8-K's parsed item headings are reconciled with the
filing index's item list (FR-EX-003).
"""

from __future__ import annotations

import logging
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.documents.blocks import linearize
from app.ingestion.documents.chunker import PARSER_VERSION, FilingMeta, chunk_filing
from app.ingestion.documents.clean import clean_tree
from app.ingestion.documents.sections import WHOLE_DOCUMENT, Section, detect_sections
from app.models import Company, Document, Filing
from app.repositories import chunks as chunk_repo
from app.repositories import filings as filing_repo
from app.repositories import quality as quality_repo
from app.repositories.ingestion import dead_letter, finish_run, start_run
from app.utils.logging import get_logger, log_event
from app.utils.storage import ObjectStorage

logger = get_logger(__name__)
PARSE_SOURCE = "parse"
LATE_FILING_NOTICE = "late_filing_notice"


@dataclass
class ChunkCounts:
    total: int = 0
    tables: int = 0
    low_confidence: bool = False


@dataclass
class ParseSummary:
    parsed: int = 0  # documents chunked by this run
    up_to_date: int = 0  # skipped: already at PARSER_VERSION
    notices: int = 0  # late-filing notices given metadata only
    failed: int = 0
    chunks: int = 0


def _period_label(filing: Filing) -> str:
    return filing.period_end.isoformat() if filing.period_end else (filing.filing_type or "")


def chunk_filing_html(html: str, meta: FilingMeta) -> list[dict[str, Any]]:
    """Pure: raw HTML -> document_chunks row-mappings."""
    return chunk_filing(linearize(clean_tree(html)), meta)


def _reconcile_items(document: Document | None, sections: list[Section], filing_type: str) -> None:
    """Compare an 8-K's parsed item headings with the filing index's list (FR-EX-003).

    Both are kept. The index list classifies the filing (it is what `filings.items` holds); the
    parsed headings bound the text. A disagreement is flagged on the document and logged.
    """
    if document is None or not filing_type.startswith("8-K"):
        return
    metadata = dict(document.doc_metadata or {})
    parsed = sorted({s.item_code for s in sections} - {WHOLE_DOCUMENT})
    indexed = metadata.get("items_metadata")
    mismatch = indexed is not None and set(indexed) != set(parsed)
    metadata.update(items_parsed=parsed, items_mismatch=mismatch)
    document.doc_metadata = metadata
    if mismatch:
        log_event(
            logger,
            logging.WARNING,
            "parse.8k_items_mismatch",
            document_id=document.id,
            items_metadata=indexed,
            items_parsed=parsed,
        )


def _chunk_document(
    session: Session,
    *,
    document: Document | None,
    meta: FilingMeta,
    raw: bytes,
    accession: str | None,
) -> ChunkCounts:
    counts = ChunkCounts()
    blocks = linearize(clean_tree(raw.decode("utf-8", errors="ignore")))
    section_result = detect_sections(blocks, meta.filing_type)
    counts.low_confidence = section_result.low_confidence
    if section_result.low_confidence:
        quality_repo.record_issue(
            session,
            company_id=meta.company_id,
            metric_name=None,
            period=meta.filing_type,
            issue_code="LOW_PARSE_CONFIDENCE",
            details={"accession": accession, "confidence": section_result.confidence},
        )
    _reconcile_items(document, section_result.sections, meta.filing_type)
    rows = chunk_filing(blocks, meta)
    counts.total = chunk_repo.replace_document_chunks(
        session, document_id=meta.document_id, rows=rows
    )
    counts.tables = sum(1 for r in rows if r["chunk_type"] == "table")
    if document is not None:
        document.parser_version = PARSER_VERSION
    return counts


def _run(session: Session, company_id: int, payload_ref: str, work: Any) -> ChunkCounts:
    """One parse with run tracking; a failure is dead-lettered, never raised (ING-005)."""
    run = start_run(session, source=PARSE_SOURCE, company_id=company_id)
    try:
        with session.begin_nested():  # a failed parse rolls back only its own writes
            counts: ChunkCounts = work()
        finish_run(
            session, run, status="success", counts={"chunks": counts.total, "tables": counts.tables}
        )
        return counts
    except Exception as exc:
        dead_letter(
            session,
            source=PARSE_SOURCE,
            payload_ref=payload_ref,
            error=f"{type(exc).__name__}: {exc}",
        )
        finish_run(session, run, status="failed", counts={}, error=str(exc))
        log_event(logger, logging.ERROR, "parse.failed", payload_ref=payload_ref, error=str(exc))
        return ChunkCounts()


def _company_name(session: Session, company_id: int) -> str:
    company = session.scalar(select(Company).where(Company.id == company_id))
    if company is None:
        raise ValueError(f"company {company_id} not found")
    return company.name


def parse_and_chunk(
    session: Session,
    filing: Filing,
    *,
    storage: ObjectStorage,
    html_bytes: bytes | None = None,
) -> ChunkCounts:
    """Parse one filing and persist its chunks. Records a run; failures are isolated."""

    def work() -> ChunkCounts:
        document = session.get(Document, filing.document_id)
        if document is not None and document.document_type == LATE_FILING_NOTICE:
            return _note_late_filing(document, filing)
        raw = (
            html_bytes
            if html_bytes is not None
            else storage.get(filing.raw_document_location or "")
        )
        meta = FilingMeta(
            document_id=filing.document_id,
            company_id=filing.company_id,
            company_name=_company_name(session, filing.company_id),
            filing_type=filing.filing_type or "",
            period_label=_period_label(filing),
            filing_date=filing.filing_date,
            period_end=filing.period_end,
        )
        return _chunk_document(
            session, document=document, meta=meta, raw=raw, accession=filing.accession_number
        )

    return _run(session, filing.company_id, filing.accession_number or str(filing.id), work)


def _note_late_filing(document: Document, filing: Filing) -> ChunkCounts:
    """An NT 10-K / NT 10-Q: record what it is late for, nothing to chunk or embed (FR-EX-014)."""
    form = filing.filing_type or ""
    document.doc_metadata = {
        **(document.doc_metadata or {}),
        "notice_for": form.removeprefix("NT ").strip(),
        "period_end": filing.period_end.isoformat() if filing.period_end else None,
    }
    document.parser_version = PARSER_VERSION
    return ChunkCounts()


def parse_exhibit(session: Session, document: Document, *, storage: ObjectStorage) -> ChunkCounts:
    """Parse an EX-99 press release stored as an `earnings_release` document (FR-EX-006)."""

    def work() -> ChunkCounts:
        metadata = document.doc_metadata or {}
        published = document.published_at.date() if document.published_at else None
        meta = FilingMeta(
            document_id=document.id,
            company_id=document.company_id,
            company_name=_company_name(session, document.company_id),
            filing_type=str(metadata.get("exhibit_type") or "EX-99"),
            period_label=published.isoformat() if published else "",
            filing_date=published,
            tier=document.source_tier,
        )
        raw = storage.get(document.raw_document_location or "")
        return _chunk_document(
            session,
            document=document,
            meta=meta,
            raw=raw,
            accession=str(metadata.get("parent_accession") or ""),
        )

    return _run(session, document.company_id, f"document:{document.id}", work)


def parse_company_documents(
    session: Session,
    company_id: int,
    *,
    storage: ObjectStorage,
    filing_types: Collection[str] | None = None,
) -> ParseSummary:
    """Parse every stored document of a company that is not yet at `PARSER_VERSION`.

    Filings (10-K, 10-Q, 8-K, proxies), late-filing notices (metadata only) and EX-99 exhibits.
    `filing_types` narrows to filings of those forms (`make reparse-8k`). Safe to re-run: a
    second run finds everything current and parses nothing.
    """
    summary = ParseSummary()
    for document, filing in filing_repo.parseable_documents(
        session, company_id=company_id, filing_types=filing_types
    ):
        if document.parser_version == PARSER_VERSION:
            summary.up_to_date += 1
            continue
        if filing is not None:
            counts = parse_and_chunk(session, filing, storage=storage)
        else:
            counts = parse_exhibit(session, document, storage=storage)
        if document.parser_version != PARSER_VERSION:
            summary.failed += 1
        elif document.document_type == LATE_FILING_NOTICE:
            summary.notices += 1
        else:
            summary.parsed += 1
            summary.chunks += counts.total
    return summary
