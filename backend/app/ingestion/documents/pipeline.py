"""Document parse & chunk pipeline (Phase 2a).

Reads a filing's raw HTML (from object storage), cleans it, detects sections, chunks it
(section-aware, tables as first-class chunks), and persists `document_chunks`. Records an
ingestion run and flags low-confidence section parses / iXBRL discrepancies into
`data_quality_issues`. `embedding` stays NULL (Phase 2b). Idempotent (DP-006).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.documents.blocks import linearize
from app.ingestion.documents.chunker import PARSER_VERSION, FilingMeta, chunk_filing
from app.ingestion.documents.clean import clean_tree
from app.ingestion.documents.sections import detect_sections
from app.models import Company, Filing
from app.repositories import chunks as chunk_repo
from app.repositories import quality as quality_repo
from app.repositories.ingestion import dead_letter, finish_run, start_run
from app.utils.logging import get_logger, log_event
from app.utils.storage import ObjectStorage

logger = get_logger(__name__)
PARSE_SOURCE = "parse"


@dataclass
class ChunkCounts:
    total: int = 0
    tables: int = 0
    low_confidence: bool = False


def _period_label(filing: Filing) -> str:
    return filing.period_end.isoformat() if filing.period_end else (filing.filing_type or "")


def chunk_filing_html(html: str, meta: FilingMeta) -> list[dict[str, Any]]:
    """Pure: raw HTML -> document_chunks row-mappings."""
    return chunk_filing(linearize(clean_tree(html)), meta)


def parse_and_chunk(
    session: Session,
    filing: Filing,
    *,
    storage: ObjectStorage,
    html_bytes: bytes | None = None,
) -> ChunkCounts:
    """Parse one filing and persist its chunks. Records a run; failures are isolated."""
    counts = ChunkCounts()
    run = start_run(session, source=PARSE_SOURCE, company_id=filing.company_id)
    try:
        company = session.scalar(select(Company).where(Company.id == filing.company_id))
        if company is None:
            raise ValueError(f"company {filing.company_id} not found")
        raw = (
            html_bytes
            if html_bytes is not None
            else storage.get(filing.raw_document_location or "")
        )
        html = raw.decode("utf-8", errors="ignore")

        tree = clean_tree(html)
        blocks = linearize(tree)
        section_result = detect_sections(blocks, filing.filing_type or "")
        counts.low_confidence = section_result.low_confidence
        if section_result.low_confidence:
            quality_repo.record_issue(
                session,
                company_id=filing.company_id,
                metric_name=None,
                period=filing.filing_type,
                issue_code="LOW_PARSE_CONFIDENCE",
                details={
                    "accession": filing.accession_number,
                    "confidence": section_result.confidence,
                },
            )

        meta = FilingMeta(
            document_id=filing.document_id,
            company_id=filing.company_id,
            company_name=company.name,
            filing_type=filing.filing_type or "",
            period_label=_period_label(filing),
            filing_date=filing.filing_date,
            period_end=filing.period_end,
        )
        rows = chunk_filing(blocks, meta)
        counts.total = chunk_repo.replace_document_chunks(
            session, document_id=filing.document_id, parser_version=PARSER_VERSION, rows=rows
        )
        counts.tables = sum(1 for r in rows if r["chunk_type"] == "table")
        finish_run(
            session, run, status="success", counts={"chunks": counts.total, "tables": counts.tables}
        )
    except Exception as exc:  # ING-005
        dead_letter(
            session,
            source=PARSE_SOURCE,
            payload_ref=filing.accession_number or str(filing.id),
            error=f"{type(exc).__name__}: {exc}",
        )
        finish_run(session, run, status="failed", counts={}, error=str(exc))
        log_event(
            logger, logging.ERROR, "parse.failed", accession=filing.accession_number, error=str(exc)
        )
    return counts
