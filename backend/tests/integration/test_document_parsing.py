"""Document parsing integration tests (Phase 2a DoD). Fixture HTML + test DB. Skips offline."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.ingestion.documents.chunker import PARSER_VERSION
from app.ingestion.documents.pipeline import parse_and_chunk
from app.ingestion.sec import ingest_company
from app.models import DocumentChunk, Filing
from app.providers.mocks._fixtures import fixture_gzip_bytes
from app.providers.sec.mock import MockSecSource
from app.utils.storage import FilesystemObjectStorage


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
def nvda_10k(session: Session, tmp_path: Path) -> Filing:
    ingest_company(session, "NVDA", sec=MockSecSource(), storage=FilesystemObjectStorage(tmp_path))
    return session.scalars(select(Filing).where(Filing.filing_type == "10-K")).one()


def _html() -> bytes:
    return fixture_gzip_bytes("nvda", "10k.htm.gz")


def _count(session: Session, document_id: int) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )
        or 0
    )


def test_parse_persists_chunks_with_null_embeddings(session: Session, nvda_10k: Filing) -> None:
    counts = parse_and_chunk(
        session, nvda_10k, storage=FilesystemObjectStorage("/dev/null"), html_bytes=_html()
    )
    assert counts.total > 100 and counts.tables > 0
    chunks = list(
        session.scalars(
            select(DocumentChunk).where(DocumentChunk.document_id == nvda_10k.document_id)
        )
    )
    assert all(c.embedding is None for c in chunks)  # embeddings are Phase 2b
    assert any(c.chunk_type == "table" for c in chunks)
    assert all(c.parser_version == PARSER_VERSION for c in chunks)


def test_reparse_is_idempotent(session: Session, nvda_10k: Filing) -> None:
    parse_and_chunk(
        session, nvda_10k, storage=FilesystemObjectStorage("/dev/null"), html_bytes=_html()
    )
    first = _count(session, nvda_10k.document_id)
    first_ids = {
        c.paragraph_id
        for c in session.scalars(
            select(DocumentChunk).where(DocumentChunk.document_id == nvda_10k.document_id)
        )
    }
    parse_and_chunk(
        session, nvda_10k, storage=FilesystemObjectStorage("/dev/null"), html_bytes=_html()
    )
    assert _count(session, nvda_10k.document_id) == first  # no duplicate chunks (DP-006)
    second_ids = {
        c.paragraph_id
        for c in session.scalars(
            select(DocumentChunk).where(DocumentChunk.document_id == nvda_10k.document_id)
        )
    }
    assert first_ids == second_ids  # identical IDs on reprocessing


def test_generated_tsv_is_populated(session: Session, nvda_10k: Filing) -> None:
    parse_and_chunk(
        session, nvda_10k, storage=FilesystemObjectStorage("/dev/null"), html_bytes=_html()
    )
    # The generated tsvector column (Phase 0b) fills from text, ready for keyword search (Phase 2b).
    row = session.scalars(
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id == nvda_10k.document_id, DocumentChunk.chunk_type == "text"
        )
        .limit(1)
    ).first()
    assert row is not None and row.tsv is not None
