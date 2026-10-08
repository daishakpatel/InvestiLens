"""SEC ingestion integration tests (Phase 1a DoD).

Run the real pipeline against the mock SEC source + a temp object store + the throwaway test DB.
Covers population, idempotency, dead-lettering with failure isolation, and the poller. Skips
offline (no DB) via the integration conftest.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.ingestion.sec import ingest_company
from app.ingestion.sec.poller import find_new_accessions
from app.models import (
    Company,
    CompanyIdentifier,
    DataFreshness,
    Document,
    Filing,
    FinancialFact,
    IngestionDeadLetter,
    IngestionRun,
)
from app.providers.sec.base import FilingRef
from app.providers.sec.mock import MockSecSource
from app.utils.storage import FilesystemObjectStorage

NVDA_CIK = "0001045810"


@pytest.fixture(scope="module")
def _migrated(test_db_url: str) -> None:
    from tests.integration.conftest import _MIGRATIONS_DIR

    cfg = Config()
    cfg.set_main_option("script_location", _MIGRATIONS_DIR)
    cfg.set_main_option("sqlalchemy.url", test_db_url)
    command.upgrade(cfg, "head")


@pytest.fixture
def session(_migrated: None, test_engine: Engine) -> Iterator[Session]:
    """A session whose changes are rolled back after each test (isolation)."""
    with Session(test_engine) as s:
        yield s
        s.rollback()


@pytest.fixture
def storage(tmp_path: Path) -> FilesystemObjectStorage:
    return FilesystemObjectStorage(tmp_path)


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_ingest_populates_all_tables(session: Session, storage: FilesystemObjectStorage) -> None:
    counts = ingest_company(session, "NVDA", sec=MockSecSource(), storage=storage)
    assert counts.filings_ingested == 3
    assert counts.facts > 1000 and counts.dead_letters == 0

    # OBS-002/§28.2: a successful ingest must leave data_freshness fresh — this was a real gap
    # found in the Phase 5c audit (unlike prices/news, SEC ingestion never wrote data_freshness
    # at all, so the API could never tell a healthy company from one that never ingested).
    company = session.scalars(select(Company)).one()
    freshness = session.scalar(
        select(DataFreshness).where(
            DataFreshness.company_id == company.id, DataFreshness.source == "sec"
        )
    )
    assert freshness is not None and freshness.status == "fresh"
    assert freshness.last_success_at is not None

    assert _count(session, Company) == 1
    assert _count(session, CompanyIdentifier) == 2  # ticker + cik
    assert _count(session, Document) == 3
    assert _count(session, Filing) == 3
    assert _count(session, FinancialFact) == counts.facts

    filing = session.scalars(select(Filing).where(Filing.filing_type == "10-K")).one()
    assert filing.accession_number and filing.content_hash and filing.source_url
    assert filing.raw_document_location  # raw preserved (ING-008)

    eightk = session.scalars(select(Filing).where(Filing.filing_type == "8-K")).one()
    assert eightk.items and "9.01" in eightk.items  # 8-K item codes populated

    fact = session.scalars(select(FinancialFact).limit(1)).one()
    assert fact.accession_number and fact.concept_tag


def test_reingest_is_idempotent(session: Session, storage: FilesystemObjectStorage) -> None:
    first = ingest_company(session, "NVDA", sec=MockSecSource(), storage=storage)
    filings_after_first = _count(session, Filing)
    facts_after_first = _count(session, FinancialFact)

    second = ingest_company(session, "NVDA", sec=MockSecSource(), storage=storage)
    assert second.filings_ingested == 0
    assert second.filings_skipped == 3
    assert _count(session, Filing) == filings_after_first  # no duplicate filings (ING-001)
    assert _count(session, FinancialFact) == facts_after_first  # facts replaced, not duplicated
    assert first.facts == second.facts


class _FailOn8KSource(MockSecSource):
    """A mock whose 8-K document fetch fails, to exercise dead-lettering."""

    def fetch_document(self, ref: FilingRef) -> bytes:
        if ref.form == "8-K":
            raise RuntimeError("simulated download failure")
        return super().fetch_document(ref)


def test_partial_failure_is_dead_lettered(
    session: Session, storage: FilesystemObjectStorage
) -> None:
    counts = ingest_company(session, "NVDA", sec=_FailOn8KSource(), storage=storage)
    # The 8-K failed, but the 10-K and 10-Q still landed (savepoint isolation, ING-005).
    assert counts.filings_ingested == 2
    assert counts.dead_letters == 1
    assert _count(session, Filing) == 2
    dead = session.scalars(select(IngestionDeadLetter)).all()
    assert len(dead) == 1 and "simulated download failure" in (dead[0].error or "")

    run = session.scalars(select(IngestionRun).order_by(IngestionRun.id.desc())).first()
    assert run is not None and run.status == "partial"


def test_unknown_ticker_raises(session: Session, storage: FilesystemObjectStorage) -> None:
    with pytest.raises(ValueError, match="unknown ticker"):
        ingest_company(session, "ZZZZ", sec=MockSecSource(), storage=storage)


class _OutageSecSource(MockSecSource):
    """Simulates SEC EDGAR being unreachable (HardenedHttpClient exhausting retries) for a known
    company — distinct from the unknown-ticker case above, which is a client error, not an
    outage."""

    def list_filings(self, cik: str) -> Sequence[FilingRef]:
        raise RuntimeError("simulated SEC EDGAR outage")


def test_provider_outage_degrades_without_crashing(
    session: Session, storage: FilesystemObjectStorage
) -> None:
    """§28.2 'SEC unavailable': a provider outage must never crash the caller or leave the run
    stuck — it records a failed run, dead-letters, and marks data_freshness failed so the API
    can show 'previously cached data' instead of silently looking healthy forever."""
    counts = ingest_company(session, "NVDA", sec=_OutageSecSource(), storage=storage)
    assert counts.filings_ingested == 0  # degraded, not crashed

    company = session.scalars(select(Company)).one()
    run = session.scalars(select(IngestionRun).where(IngestionRun.company_id == company.id)).one()
    assert run.status == "failed"

    freshness = session.scalar(
        select(DataFreshness).where(
            DataFreshness.company_id == company.id, DataFreshness.source == "sec"
        )
    )
    assert freshness is not None and freshness.status == "failed"
    assert freshness.last_success_at is None

    dead = session.scalars(select(IngestionDeadLetter)).all()
    assert any("outage" in (d.error or "") for d in dead)


def test_poller_detects_new_then_none(session: Session, storage: FilesystemObjectStorage) -> None:
    source = MockSecSource()
    before: Sequence[str] = find_new_accessions(session, NVDA_CIK, sec=source)
    assert len(before) == 3  # nothing ingested yet
    ingest_company(session, "NVDA", sec=source, storage=storage)
    after = find_new_accessions(session, NVDA_CIK, sec=source)
    assert after == []  # all ingested
