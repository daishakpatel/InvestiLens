"""Run the red-flag taxonomy over a company's filings and store what fires (Phase 7e, FR-RF-007).

Runs after parsing (the `parse_documents` task and the refresh chain) and nightly, and from
`make redflags-backfill`. Idempotent: an event already stored under the current taxonomy
version is left alone (unique key, ON CONFLICT DO NOTHING). A new taxonomy version writes new
rows and keeps the first-detection time of events an older version already found, so a re-run
never looks like news to the alert loop. Each filing is evaluated on its own; one failure is
dead-lettered and the scan continues. The pass is recorded in `ingestion_runs` (source
`red_flags`), which is what the API's "scanned through" date reads.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, Document, DocumentChunk, Filing, FinancialMetric
from app.redflags import taxonomy as tx
from app.repositories import red_flags as repo
from app.repositories.ingestion import dead_letter, finish_run, start_run
from app.utils.logging import get_logger, log_event

logger = get_logger(__name__)

SCANNED_FORMS = tx.EIGHT_K_FORMS | tx.LATE_NOTICE_FORMS | tx.PERIODIC_FORMS
MAX_RESTATED = 10  # changed values quoted per amended filing


@dataclass
class ScanSummary:
    filings: int = 0
    new_flags: int = 0
    failed: int = 0


def _paragraphs(session: Session, document_ids: list[int]) -> dict[int, list[tx.Paragraph]]:
    rows = session.execute(
        select(
            DocumentChunk.document_id,
            DocumentChunk.paragraph_id,
            DocumentChunk.chunk_metadata,
            DocumentChunk.text,
        )
        .where(DocumentChunk.document_id.in_(document_ids), DocumentChunk.chunk_type == "text")
        .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
    )
    out: dict[int, list[tx.Paragraph]] = defaultdict(list)
    for document_id, paragraph_id, meta, text in rows:
        out[document_id].append(tx.Paragraph(paragraph_id, (meta or {}).get("section_key"), text))
    return out


def _beneish_by_accession(session: Session, company_id: int) -> dict[str, dict[str, str]]:
    """Above-threshold Beneish years, keyed by the accession of that year's 10-K (the filing
    the base figures were read from)."""
    above = {
        row.fiscal_year: row
        for row in session.scalars(
            select(FinancialMetric).where(
                FinancialMetric.company_id == company_id,
                FinancialMetric.metric_name == "beneish_m",
                FinancialMetric.period_type == "FY",
                FinancialMetric.metric_value.is_not(None),
            )
        )
        if (row.quality_flags or {}).get("band") == "above_threshold"
    }
    out: dict[str, dict[str, str]] = {}
    for fiscal_year, accession in session.execute(
        select(FinancialMetric.fiscal_year, FinancialMetric.as_reported_accession).where(
            FinancialMetric.company_id == company_id,
            FinancialMetric.metric_name == "revenue",
            FinancialMetric.period_type == "FY",
            FinancialMetric.is_latest.is_(True),
        )
    ):
        row = above.get(fiscal_year)
        if row is not None and accession and row.metric_value is not None:
            out[accession] = {
                "score": f"{row.metric_value:.2f}",
                "fiscal_year": str(fiscal_year),
                "source_id": row.source_id or "",
            }
    return out


def _restated_by_accession(
    session: Session, company_id: int, accessions: list[str]
) -> dict[str, list[dict[str, str]]]:
    """For amended filings: canonical as-reported values that differ from the original filing's
    value for the same metric and period (Phase 1b keeps every as-reported row, DR-023)."""
    if not accessions:
        return {}
    rows = session.scalars(
        select(FinancialMetric)
        .where(
            FinancialMetric.company_id == company_id,
            FinancialMetric.is_derived.is_(False),
            FinancialMetric.period_type == "FY",
        )
        .order_by(FinancialMetric.id)
    ).all()
    by_period: dict[tuple[str, str], list[FinancialMetric]] = defaultdict(list)
    for row in rows:
        by_period[(row.metric_name, row.period)].append(row)
    out: dict[str, list[dict[str, str]]] = defaultdict(list)
    for (metric, period), versions in by_period.items():
        originals = [
            v.metric_value
            for v in versions
            if v.as_reported_accession not in accessions and v.metric_value is not None
        ]
        if not originals:
            continue
        for v in versions:
            # A value equal to any original is a repeated comparative, not a restatement.
            if (
                v.as_reported_accession in accessions
                and v.metric_value is not None
                and v.metric_value not in originals
            ):
                out[v.as_reported_accession or ""].append(
                    {
                        "metric": metric,
                        "period": period,
                        "before": str(originals[0]),
                        "after": str(v.metric_value),
                    }
                )
    return {acc: changes[:MAX_RESTATED] for acc, changes in out.items()}


def _evidence(
    filing: Filing,
    document: Document,
    paragraphs: list[tx.Paragraph],
    beneish: dict[str, dict[str, str]],
    restated: dict[str, list[dict[str, str]]],
) -> tx.FilingEvidence:
    meta = document.doc_metadata or {}
    # The filing index classifies an 8-K; parsed headings are the fallback (FR-EX-003).
    items = filing.items or meta.get("items_parsed") or []
    return tx.FilingEvidence(
        filing_type=filing.filing_type,
        items=frozenset(str(i) for i in items),
        paragraphs=tuple(paragraphs),
        notice_for=meta.get("notice_for"),
        period_end=filing.period_end.isoformat() if filing.period_end else None,
        beneish=beneish.get(filing.accession_number),
        restated=tuple(restated.get(filing.accession_number, [])),
    )


def scan_company(session: Session, company: Company) -> ScanSummary:
    """Evaluate every scanned form of `company` and store new flags. Safe to re-run."""
    run = start_run(session, source=repo.SCAN_SOURCE, company_id=company.id)
    summary = ScanSummary()
    pairs = session.execute(
        select(Filing, Document)
        .join(Document, Document.id == Filing.document_id)
        .where(Filing.company_id == company.id, Filing.filing_type.in_(SCANNED_FORMS))
        .order_by(Filing.filing_date, Filing.id)
    ).all()
    paragraphs = _paragraphs(session, [d.id for _, d in pairs])
    beneish = _beneish_by_accession(session, company.id)
    amended = [f.accession_number for f, _ in pairs if f.filing_type.endswith("/A")]
    restated = _restated_by_accession(session, company.id, amended)
    first_seen = repo.first_detections(session, company.id)
    now = datetime.now(UTC)
    rows: list[dict[str, Any]] = []
    for filing, document in pairs:
        summary.filings += 1
        try:
            evidence = _evidence(
                filing, document, paragraphs.get(document.id, []), beneish, restated
            )
            for rule, match in tx.evaluate(evidence):
                key = (rule.key, filing.id, match.paragraph_id)
                rows.append(
                    {
                        "company_id": company.id,
                        "rule_key": rule.key,
                        "taxonomy_version": tx.TAXONOMY_VERSION,
                        "filing_id": filing.id,
                        "document_id": document.id,
                        "paragraph_id": match.paragraph_id,
                        "detected_at": first_seen.get(key, now),
                        "event_date": filing.filing_date
                        or (document.published_at.date() if document.published_at else None),
                        "severity": rule.severity,
                        "snippet": match.snippet,
                        "payload": match.payload,
                    }
                )
        except Exception as exc:  # one bad filing never stops the scan (ING-005)
            summary.failed += 1
            dead_letter(
                session,
                source=repo.SCAN_SOURCE,
                payload_ref=filing.accession_number,
                error=f"{type(exc).__name__}: {exc}",
            )
            log_event(
                logger, logging.ERROR, "redflags.filing_failed", accession=filing.accession_number
            )
    summary.new_flags = repo.insert_flags(session, rows)
    finish_run(
        session,
        run,
        status="success",
        counts={
            "filings": summary.filings,
            "new_flags": summary.new_flags,
            "failed": summary.failed,
        },
    )
    log_event(logger, logging.INFO, "redflags.scanned", ticker=company.ticker, **vars(summary))
    return summary
