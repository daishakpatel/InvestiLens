"""Phase 7c integration: exhibits, extra forms, re-parsing and its citation guarantees.

Ingests the NVDA fixtures (mock SEC: an earnings 8-K with EX-99.1/99.2, a 5.02 8-K, DEF 14A,
DEFA14A, and synthetic NT 10-K / NT 10-Q / 8-K/A) and parses them into the throwaway test DB.
Skips offline. Refs: FR-EX-001 … FR-EX-015, DR-EX-001 … DR-EX-003, CIT-006.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, update
from sqlalchemy.orm import Session
from structlog.testing import capture_logs

from app.citation.resolver import resolve_source
from app.config import get_settings
from app.db import get_db
from app.ingestion.documents import chunker
from app.ingestion.documents import pipeline as doc_pipeline
from app.ingestion.documents.chunker import PARSER_VERSION
from app.ingestion.documents.pipeline import parse_company_documents
from app.ingestion.sec import ingest_company
from app.ingestion.sec.poller import find_new_accessions
from app.main import app
from app.models import Company, Document, DocumentChunk, Filing, IngestionDeadLetter
from app.providers.sec.base import ExhibitRef
from app.providers.sec.mock import MockSecSource
from app.rag.search import keyword_search
from app.repositories import embeddings as embed_repo
from app.utils.storage import FilesystemObjectStorage

EARNINGS_8K = "0001045810-26-000073"
OFFICER_8K = "0001045810-26-000024"
_P = "/api/v1"


@pytest.fixture(scope="module")
def _migrated(test_db_url: str) -> None:
    from tests.integration.conftest import _MIGRATIONS_DIR

    cfg = Config()
    cfg.set_main_option("script_location", _MIGRATIONS_DIR)
    cfg.set_main_option("sqlalchemy.url", test_db_url)
    command.upgrade(cfg, "head")


@pytest.fixture
def session(_migrated: None, test_engine: Engine) -> Iterator[Session]:
    with Session(test_engine) as s:
        yield s
        s.rollback()


@pytest.fixture
def storage(tmp_path: Path) -> FilesystemObjectStorage:
    return FilesystemObjectStorage(tmp_path)


def _nvda(session: Session, storage: FilesystemObjectStorage) -> Company:
    ingest_company(session, "NVDA", sec=MockSecSource(), storage=storage)
    return session.scalars(select(Company).where(Company.ticker == "NVDA")).one()


def _documents(session: Session, company: Company, document_type: str) -> list[Document]:
    return list(
        session.scalars(
            select(Document).where(
                Document.company_id == company.id, Document.document_type == document_type
            )
        )
    )


def _filing_document(session: Session, accession: str) -> Document:
    filing = session.scalars(select(Filing).where(Filing.accession_number == accession)).one()
    document = session.get(Document, filing.document_id)
    assert document is not None
    return document


def _chunks(session: Session, document_id: int) -> list[DocumentChunk]:
    return list(
        session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
    )


def test_earnings_8k_exhibits_become_tier_two_releases(
    session: Session, storage: FilesystemObjectStorage
) -> None:
    # FR-EX-006/007/008/015: the poller sees the new earnings 8-K; the refresh chain it starts
    # (ingest, then parse) stores EX-99.1 and EX-99.2 as earnings_release documents (tier 2,
    # published at the 8-K's acceptance) and chunks them like any filing.
    assert EARNINGS_8K in find_new_accessions(session, "0001045810", sec=MockSecSource())
    company = _nvda(session, storage)
    releases = {
        (d.doc_metadata or {})["exhibit_type"]: d
        for d in _documents(session, company, "earnings_release")
    }
    assert set(releases) == {"EX-99.1", "EX-99.2"}
    release = releases["EX-99.1"]
    assert release.source_tier == 2 and release.published_at is not None
    assert release.doc_metadata == {
        "parent_accession": EARNINGS_8K,
        "exhibit_type": "EX-99.1",
        "filename": "q2fy27pr.htm",
        "size_bytes": 341113,
    }
    assert release.source_url and release.source_url.endswith("/q2fy27pr.htm")
    parent = _filing_document(session, EARNINGS_8K)
    assert parent.published_at == release.published_at  # the 8-K's acceptance time
    assert (parent.doc_metadata or {})["exhibits_checked"] is True
    # The 8.01 8-K has no EX-99 and the 5.02 one is not an exhibit-bearing item: nothing stored.
    assert len(_documents(session, company, "earnings_release")) == 2

    summary = parse_company_documents(session, company.id, storage=storage)
    assert summary.failed == 0
    chunks = _chunks(session, release.id)
    assert chunks and all(c.tier == 2 and c.filing_type == "EX-99.1" for c in chunks)
    revenue = [c for c in chunks if "| Revenue | $96,221 |" in c.text]
    assert revenue and "| Diluted earnings per share | $2.46 |" in revenue[0].text
    # Retrievable through RAG keyword search, and citable as an earnings release (tier 2).
    hits = keyword_search(
        session, query="diluted earnings per share", company_id=company.id, limit=50
    )
    assert any(h.chunk_id in {c.id for c in chunks} for h in hits)
    detail = resolve_source(session, revenue[0].paragraph_id or "")
    assert detail is not None and detail.source.source_type == "earnings_release"
    assert detail.source.tier == 2


def test_extra_forms_are_listed_with_their_document_type(
    session: Session, storage: FilesystemObjectStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    # FR-EX-009: DEF 14A, DEFA14A (supplemental), NT 10-K / NT 10-Q (late_filing_notice), 8-K/A.
    company = _nvda(session, storage)
    monkeypatch.setattr(session, "commit", session.flush)
    app.dependency_overrides[get_db] = lambda: session
    try:
        listed = TestClient(app).get(f"{_P}/companies/NVDA/filings", params={"limit": 50}).json()
    finally:
        app.dependency_overrides.clear()
    types = {f["filing_type"]: f["document_type"] for f in listed}
    assert types == {
        "10-K": "filing",
        "10-Q": "filing",
        "8-K": "filing",
        "8-K/A": "filing",
        "DEF 14A": "filing",
        "DEFA14A": "filing",
        "NT 10-K": "late_filing_notice",
        "NT 10-Q": "late_filing_notice",
    }
    supplemental = _filing_document(session, "0001045810-26-000037")
    assert (supplemental.doc_metadata or {})["supplemental"] is True
    amendment = session.scalars(select(Filing).where(Filing.filing_type == "8-K/A")).one()
    assert amendment.items == ["5.02"]

    # A late-filing notice gets metadata only: no chunks, so no embedding spend (FR-EX-014).
    summary = parse_company_documents(session, company.id, storage=storage)
    assert summary.notices == 2
    for notice in _documents(session, company, "late_filing_notice"):
        assert notice.parser_version == PARSER_VERSION and _chunks(session, notice.id) == []
        assert (notice.doc_metadata or {})["notice_for"] in {"10-K", "10-Q"}
    proxy = _filing_document(session, "0001045810-26-000036")
    assert _chunks(session, proxy.id)  # the DEF 14A is chunked (its content is parsed in 7g)


def test_10q_part_one_item_one_is_retrievable(
    session: Session, storage: FilesystemObjectStorage
) -> None:
    # FR-EX-012 regression: the 10-Q's financial-statement notes are chunked and searchable.
    company = _nvda(session, storage)
    parse_company_documents(session, company.id, storage=storage, filing_types=["10-Q"])
    tenq = session.scalars(select(Filing).where(Filing.filing_type == "10-Q")).one()
    notes = [
        c
        for c in _chunks(session, tenq.document_id)
        if (c.chunk_metadata or {}).get("section_key") == "10q_part1_item1_notes"
    ]
    assert len(notes) > 20
    hits = keyword_search(
        session,
        query="condensed consolidated financial statements",
        company_id=company.id,
        limit=100,
    )
    assert {h.chunk_id for h in hits} & {c.id for c in notes}


def test_parse_skips_documents_already_at_the_current_version(
    session: Session, storage: FilesystemObjectStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    # FR-EX-014: a second run parses nothing (counted at the chunker).
    company = _nvda(session, storage)
    calls: list[str] = []
    real = chunker.chunk_filing

    def counting(blocks: Any, meta: Any) -> list[dict[str, Any]]:
        calls.append(meta.filing_type)
        return real(blocks, meta)

    monkeypatch.setattr(doc_pipeline, "chunk_filing", counting)
    first = parse_company_documents(session, company.id, storage=storage)
    parsed_once = len(calls)
    assert parsed_once == first.parsed == 10  # 8 chunked filings + 2 exhibits; 2 notices aside
    second = parse_company_documents(session, company.id, storage=storage)
    assert len(calls) == parsed_once  # no parser invocation
    assert (second.parsed, second.up_to_date) == (0, first.parsed + first.notices)


def _stale_8ks(session: Session, company: Company) -> dict[int, str]:
    """Make the 8-Ks look like they were parsed by v1, with a v1-style chunk each."""
    ids = {
        f.document_id: f.accession_number
        for f in session.scalars(
            select(Filing).where(Filing.company_id == company.id, Filing.filing_type == "8-K")
        )
    }
    session.execute(
        update(Document).where(Document.id.in_(ids)).values(parser_version="sec-ingest-v1")
    )
    for document_id in ids:
        session.add(
            DocumentChunk(
                document_id=document_id,
                company_id=company.id,
                chunk_index=999,
                chunk_type="text",
                text="Old v1 chunk under the collapsed item code.",
                paragraph_id=f"{document_id}_5_0",  # v1 collapsed "5.02" to "5"
                parent_section_id=f"{document_id}_5",
                parser_version="doc-parse-v1",
                filing_type="8-K",
            )
        )
    session.flush()
    return ids


def test_reparse_8k_is_idempotent_and_old_citations_fail_loudly(
    session: Session, storage: FilesystemObjectStorage
) -> None:
    # FR-EX-004, DR-EX-001, CIT-006: `make reparse-8k` re-chunks only stale 8-Ks; a second run
    # changes nothing; an old chunk ID resolves to not-found rather than to other text.
    company = _nvda(session, storage)
    parse_company_documents(session, company.id, storage=storage)
    stale = _stale_8ks(session, company)
    assert resolve_source(session, f"{next(iter(stale))}_5_0") is not None  # before: resolves
    tenk = session.scalars(select(Filing).where(Filing.filing_type == "10-K")).one()
    tenk_ids = [c.paragraph_id for c in _chunks(session, tenk.document_id)]

    first = parse_company_documents(
        session, company.id, storage=storage, filing_types=["8-K", "8-K/A"]
    )
    assert first.parsed == len(stale)
    for document_id in stale:
        assert session.get(Document, document_id).parser_version == PARSER_VERSION  # type: ignore[union-attr]
        assert resolve_source(session, f"{document_id}_5_0") is None  # not-found, loudly
        assert all(c.parser_version == PARSER_VERSION for c in _chunks(session, document_id))
    officer = _filing_document(session, OFFICER_8K)
    codes = {c.paragraph_id.split("_")[1] for c in _chunks(session, officer.id) if c.paragraph_id}
    assert codes == {"5.02", "9.01"}
    snapshot = {d: [(c.paragraph_id, c.content_hash) for c in _chunks(session, d)] for d in stale}

    second = parse_company_documents(
        session, company.id, storage=storage, filing_types=["8-K", "8-K/A"]
    )
    assert second.parsed == 0 and second.up_to_date == len(stale) + 1  # + the 8-K/A
    assert snapshot == {
        d: [(c.paragraph_id, c.content_hash) for c in _chunks(session, d)] for d in stale
    }
    assert [c.paragraph_id for c in _chunks(session, tenk.document_id)] == tenk_ids  # untouched


def test_items_mismatch_is_flagged_and_logged(
    session: Session, storage: FilesystemObjectStorage
) -> None:
    # FR-EX-003: both lists are kept; the index list classifies, the headings bound the text.
    company = _nvda(session, storage)
    officer = _filing_document(session, OFFICER_8K)
    officer.doc_metadata = {**(officer.doc_metadata or {}), "items_metadata": ["5.02", "7.01"]}
    agreeing = _filing_document(session, EARNINGS_8K)
    session.flush()
    with capture_logs() as logs:
        parse_company_documents(session, company.id, storage=storage, filing_types=["8-K"])
    assert (officer.doc_metadata or {})["items_mismatch"] is True
    assert (officer.doc_metadata or {})["items_parsed"] == ["5.02", "9.01"]
    assert (agreeing.doc_metadata or {})["items_mismatch"] is False
    mismatches = {e["document_id"]: e for e in logs if e["event"] == "parse.8k_items_mismatch"}
    assert mismatches[officer.id]["log_level"] == "warning"
    assert mismatches[officer.id]["items_metadata"] == ["5.02", "7.01"]
    assert agreeing.id not in mismatches
    # A real one too: EDGAR indexes the 2026-09-03 8-K as Item 8.01 only, but its text also has
    # an "Item 9.01" heading. Both lists are kept; the index list classifies the filing.
    real = _filing_document(session, "0001045810-26-000078")
    assert (real.doc_metadata or {})["items_parsed"] == ["8.01", "9.01"]
    assert real.id in mismatches


def test_reparse_keeps_embeddings_of_unchanged_text(
    session: Session, storage: FilesystemObjectStorage
) -> None:
    # DR-EX-002 (ADR-0041 cost guard): a re-parse replaces the rows, not unchanged text's vector.
    company = _nvda(session, storage)
    parse_company_documents(session, company.id, storage=storage, filing_types=["10-K"])
    tenk = session.scalars(select(Filing).where(Filing.filing_type == "10-K")).one()
    chunk = _chunks(session, tenk.document_id)[0]
    dim = get_settings().embedding_dimension
    chunk.embedding, chunk.embedding_model, chunk.embedding_dim = [0.5] * dim, "test-model", dim
    content_hash = chunk.content_hash
    session.execute(
        update(Document).where(Document.id == tenk.document_id).values(parser_version="old")
    )
    session.flush()
    session.expire_all()

    parse_company_documents(session, company.id, storage=storage, filing_types=["10-K"])
    kept = [c for c in _chunks(session, tenk.document_id) if c.content_hash == content_hash]
    assert kept and kept[0].embedding_model == "test-model" and kept[0].embedding is not None


def test_exhibit_and_proxy_embeddings_follow_the_config_flag(
    session: Session, storage: FilesystemObjectStorage
) -> None:
    # FR-EX-013: EMBED_EXHIBITS=false leaves EX-99 and DEF 14A chunks out of the embedding queue.
    company = _nvda(session, storage)
    parse_company_documents(session, company.id, storage=storage)
    gated = set(
        session.scalars(
            select(DocumentChunk.id).where(
                DocumentChunk.company_id == company.id,
                DocumentChunk.filing_type.in_(("EX-99.1", "EX-99.2", "DEF 14A", "DEFA14A")),
            )
        )
    )
    assert gated
    everything = {i for i, _ in embed_repo.fetch_pending_batch(session, model="m", limit=100_000)}
    without = {
        i
        for i, _ in embed_repo.fetch_pending_batch(
            session, model="m", limit=100_000, include_exhibits=False
        )
    }
    assert gated <= everything and not gated & without
    assert everything - gated <= without  # filings are still embedded
    assert embed_repo.count_pending(session, model="m", include_exhibits=False) >= len(without)


class _FailingExhibits(MockSecSource):
    def fetch_exhibit(self, exhibit: ExhibitRef) -> bytes:
        raise RuntimeError("simulated exhibit download failure")


class _CountingExhibits(MockSecSource):
    listings: int = 0

    def list_exhibits(self, filing: Any) -> Sequence[ExhibitRef]:
        type(self).listings += 1
        return super().list_exhibits(filing)


def test_failed_exhibit_keeps_the_filing_and_retries_next_run(
    session: Session, storage: FilesystemObjectStorage
) -> None:
    # ING-005: the 8-K is stored even though its exhibit failed; the next run fetches it, and
    # once checked the filing index is not read again (FR-EX-007 rate-limit guard).
    counts = ingest_company(session, "NVDA", sec=_FailingExhibits(), storage=storage)
    assert counts.exhibits == 0 and counts.dead_letters == 1
    assert session.scalars(select(Filing).where(Filing.accession_number == EARNINGS_8K)).one()
    dead = session.scalars(select(IngestionDeadLetter)).all()
    assert [d.payload_ref for d in dead] == [f"exhibits:{EARNINGS_8K}"]
    assert "exhibits_checked" not in (_filing_document(session, EARNINGS_8K).doc_metadata or {})

    retry = ingest_company(session, "NVDA", sec=_CountingExhibits(), storage=storage)
    assert retry.exhibits == 2 and _CountingExhibits.listings == 1
    ingest_company(session, "NVDA", sec=_CountingExhibits(), storage=storage)
    assert _CountingExhibits.listings == 1  # already checked: no second index read
    total = session.scalar(
        select(func.count())
        .select_from(Document)
        .where(Document.document_type == "earnings_release")
    )
    assert total == 2
