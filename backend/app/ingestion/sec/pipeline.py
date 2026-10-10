"""SEC ingestion pipeline (Phase 1a).

Resolves a company, discovers its filings, applies the backfill policy, downloads and stores each
new filing, extracts 8-K items and amendment links, and upserts XBRL facts — all idempotently
(ING-001) with run tracking (ING-003), dead-lettering (ING-004), and per-item failure isolation
(ING-005). One filing's failure never aborts the rest.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.cache.cache import invalidate_company
from app.config import Settings, get_settings
from app.finance.sic import sic_to_sector
from app.providers.sec import get_sec_source
from app.providers.sec.base import CompanyMetadata, CompanyRef, FilingRef, SecSource
from app.repositories import companies as company_repo
from app.repositories import facts as facts_repo
from app.repositories import filings as filing_repo
from app.repositories.freshness import record_freshness
from app.repositories.ingestion import dead_letter, finish_run, start_run
from app.utils.dates import months_ago, years_ago
from app.utils.logging import get_logger, log_event
from app.utils.storage import ObjectStorage

logger = get_logger(__name__)
PARSER_VERSION = "sec-ingest-v1"


@dataclass
class IngestCounts:
    filings_ingested: int = 0
    filings_skipped: int = 0
    facts: int = 0
    facts_skipped: int = 0
    dead_letters: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "filings_ingested": self.filings_ingested,
            "filings_skipped": self.filings_skipped,
            "facts": self.facts,
            "facts_skipped": self.facts_skipped,
            "dead_letters": self.dead_letters,
        }


def _to_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _within_backfill(ref: FilingRef, settings: Settings, today: date) -> bool:
    """ING-002 backfill window per form type."""
    filed = _to_date(ref.filing_date)
    if filed is None:
        return True  # keep undated filings; let downstream decide
    if ref.form.startswith("10-K"):
        return filed >= years_ago(today, settings.backfill_10k_years)
    if ref.form.startswith("10-Q"):
        return filed >= months_ago(today, settings.backfill_10q_quarters * 3)
    if ref.form.startswith("8-K"):
        return filed >= months_ago(today, settings.backfill_8k_months)
    return False  # other forms out of MVP scope for backfill


def _resolve_items(ref: FilingRef, document: bytes) -> list[str] | None:
    if not ref.form.startswith("8-K"):
        return None
    if ref.items:
        return list(ref.items)
    from app.ingestion.sec.items import parse_8k_items

    return parse_8k_items(document) or None


def _ingest_one_filing(
    session: Session,
    *,
    sec: SecSource,
    storage: ObjectStorage,
    company_id: int,
    ticker: str,
    ref: FilingRef,
    counts: IngestCounts,
) -> None:
    if filing_repo.filing_exists(session, ref.accession_number):
        counts.filings_skipped += 1
        return

    document = sec.fetch_document(ref)
    content_hash = hashlib.sha256(document).hexdigest()
    storage_key = f"sec/{ref.cik}/{ref.accession_number.replace('-', '')}/{ref.primary_document}"
    storage.put(storage_key, document)

    document_id = filing_repo.get_or_create_document(
        session,
        company_id=company_id,
        document_type="filing",
        source_tier=1,
        content_hash=content_hash,
        title=f"{ticker} {ref.form}",
        source_url=ref.primary_doc_url,
        raw_document_location=storage_key,
        parser_version=PARSER_VERSION,
        doc_metadata={"form": ref.form, "accession_number": ref.accession_number},
    )

    period_end = _to_date(ref.report_date)
    amends_id: int | None = None
    if ref.form.endswith("/A"):
        amends_id = filing_repo.get_filing_id_for_period(
            session, company_id=company_id, filing_type=ref.form[:-2], period_end=period_end
        )

    inserted = filing_repo.insert_filing(
        session,
        document_id=document_id,
        company_id=company_id,
        filing_type=ref.form,
        filing_date=_to_date(ref.filing_date),
        period_end=period_end,
        accession_number=ref.accession_number,
        source_url=ref.primary_doc_url,
        primary_document_url=ref.primary_doc_url,
        content_hash=content_hash,
        raw_document_location=storage_key,
        amends_filing_id=amends_id,
        items=_resolve_items(ref, document),
    )
    if inserted is not None:
        counts.filings_ingested += 1
    else:
        counts.filings_skipped += 1


def ingest_company(
    session: Session,
    ticker: str,
    *,
    sec: SecSource | None = None,
    storage: ObjectStorage,
    today: date | None = None,
) -> IngestCounts:
    """Ingest one company end-to-end. Returns per-run counts; records an `ingestion_runs` row."""
    settings = get_settings()
    sec = sec or get_sec_source()
    today = today or datetime.now(UTC).date()
    counts = IngestCounts()

    ref = _find_company_ref(sec, ticker)
    if ref is None:
        run = start_run(session, source="sec", company_id=None)
        finish_run(
            session,
            run,
            status="failed",
            counts=counts.as_dict(),
            error=f"unknown ticker: {ticker}",
        )
        raise ValueError(f"unknown ticker: {ticker}")

    # Profile enrichment from the submissions endpoint (SIC/industry/exchange/FYE): needed for
    # peer-set grouping (§37.1) and sector exposure (§37.2). A metadata-fetch failure must not
    # abort ingestion — the fields are nullable and `upsert_company` preserves any prior value.
    meta = CompanyMetadata()
    try:
        meta = sec.company_metadata(ref.cik)
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            "sec.company_metadata.failed",
            ticker=ref.ticker,
            error=str(exc),
        )
    company_id = company_repo.upsert_company(
        session,
        ticker=ref.ticker,
        cik=ref.cik,
        name=meta.name or ref.title,
        exchange=meta.exchange,
        sector=sic_to_sector(meta.sic_code),
        industry=meta.industry,
        sic_code=meta.sic_code,
        fiscal_year_end=meta.fiscal_year_end,
    )
    company_repo.upsert_identifier(
        session,
        company_id=company_id,
        identifier_type="ticker",
        identifier_value=ref.ticker,
        is_primary=True,
    )
    company_repo.upsert_identifier(
        session,
        company_id=company_id,
        identifier_type="cik",
        identifier_value=ref.cik,
    )

    run = start_run(session, source="sec", company_id=company_id)
    attempt_at = datetime.now(UTC)

    # A provider outage (SEC EDGAR down/429-exhausted) must degrade, not crash the caller or leave
    # the run stuck "running" forever with no data_freshness update (ERR-002, OBS-002/§28.2 "SEC
    # unavailable" — this was a real gap: unlike prices/news, SEC ingestion never wrote
    # data_freshness at all, so the API's freshness endpoint could never distinguish a healthy
    # company from one whose ingest has never succeeded or has been failing for days).
    try:
        filings = list(sec.list_filings(ref.cik))
    except Exception as exc:
        dead_letter(
            session, source="sec", payload_ref=ref.cik, error=f"{type(exc).__name__}: {exc}"
        )
        record_freshness(
            session,
            company_id=company_id,
            source="sec",
            status="failed",
            last_success_at=None,
            last_attempt_at=attempt_at,
            message=str(exc),
        )
        finish_run(session, run, status="failed", counts=counts.as_dict(), error=str(exc))
        log_event(
            logger, logging.ERROR, "sec.list_filings.failed", ticker=ref.ticker, error=str(exc)
        )
        return counts

    for filing in filings:
        if not _within_backfill(filing, settings, today):
            continue
        # SAVEPOINT per filing (ING-005): a failure rolls back only this filing, leaving the
        # outer transaction (run row, earlier filings) intact so we can dead-letter and continue.
        try:
            with session.begin_nested():
                _ingest_one_filing(
                    session,
                    sec=sec,
                    storage=storage,
                    company_id=company_id,
                    ticker=ref.ticker,
                    ref=filing,
                    counts=counts,
                )
        except Exception as exc:
            counts.dead_letters += 1
            dead_letter(
                session,
                source="sec",
                payload_ref=filing.accession_number,
                error=f"{type(exc).__name__}: {exc}",
            )
            log_event(
                logger,
                logging.ERROR,
                "sec.filing.failed",
                accession=filing.accession_number,
                error=str(exc),
            )

    try:
        with session.begin_nested():  # SAVEPOINT: facts failure doesn't lose the filings
            rows, skipped = _parse_facts(company_id, sec, ref.cik)
            counts.facts = facts_repo.replace_company_facts(
                session, company_id=company_id, facts=rows
            )
            counts.facts_skipped = skipped
    except Exception as exc:
        counts.facts = 0
        counts.dead_letters += 1
        dead_letter(
            session,
            source="sec",
            payload_ref=f"companyfacts:{ref.cik}",
            error=f"{type(exc).__name__}: {exc}",
        )
        log_event(logger, logging.ERROR, "sec.facts.failed", cik=ref.cik, error=str(exc))

    status = "success" if counts.dead_letters == 0 else "partial"
    record_freshness(
        session,
        company_id=company_id,
        source="sec",
        status="fresh",
        last_success_at=datetime.now(UTC),
        last_attempt_at=attempt_at,
    )
    finish_run(session, run, status=status, counts=counts.as_dict())
    # `filing.ingested` event → drop this company's cached data so the API serves fresh (CACHE-002).
    if counts.filings_ingested or counts.facts:
        invalidate_company(ref.ticker)
    log_event(logger, logging.INFO, "sec.company.ingested", ticker=ref.ticker, **counts.as_dict())
    return counts


def _find_company_ref(sec: SecSource, ticker: str) -> CompanyRef | None:
    key = ticker.strip().upper()
    for ref in sec.company_tickers():
        if ref.ticker.upper() == key or ref.cik == key.zfill(10):
            return ref
    return None


def _parse_facts(company_id: int, sec: SecSource, cik: str) -> tuple[list[dict[str, Any]], int]:
    from app.ingestion.sec.xbrl import parse_companyfacts

    return parse_companyfacts(company_id, sec.companyfacts(cik))


@dataclass
class BatchResult:
    per_company: dict[str, IngestCounts] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)


def ingest_companies(
    session_factory: Callable[[], Session],
    tickers: list[str],
    *,
    storage: ObjectStorage,
) -> BatchResult:
    """Ingest several companies; one company's failure never aborts the batch (ING-005)."""
    result = BatchResult()
    for ticker in tickers:
        try:
            with session_factory() as session:
                result.per_company[ticker] = ingest_company(session, ticker, storage=storage)
                session.commit()
        except Exception as exc:
            result.failures[ticker] = f"{type(exc).__name__}: {exc}"
            log_event(logger, logging.ERROR, "sec.company.aborted", ticker=ticker, error=str(exc))
    return result
