"""Migration up/down tests on empty and populated databases (DB-001).

Covers Phase 0b Definition of Done: the initial migration applies and reverses cleanly, the
pgvector extension and the special indexes are created, and the seed script populates every
table. References: DB-001 (migrations tested up/down), DB-003 (no float money columns),
ADR-0002/ADR-0010 (pgvector, HNSW), CIT-002 (chunk anchors).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.models import Base
from tests.integration.conftest import public_table_names

_MODEL_TABLES = set(Base.metadata.tables)


def _seed_module() -> ModuleType:
    """Import scripts/seed.py by path (it lives outside the package)."""
    seed_path = Path(__file__).resolve().parents[3] / "scripts" / "seed.py"
    spec = importlib.util.spec_from_file_location("investilens_seed", seed_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_creates_every_model_table(alembic_cfg: Config, test_engine: Engine) -> None:
    command.upgrade(alembic_cfg, "head")
    tables = public_table_names(test_engine)
    assert tables >= _MODEL_TABLES  # DB-001: every model table exists
    assert "alembic_version" in tables


def test_pgvector_extension_and_special_indexes(alembic_cfg: Config, test_engine: Engine) -> None:
    command.upgrade(alembic_cfg, "head")
    with test_engine.connect() as conn:
        ext = conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar()
        assert ext == 1  # ADR-0002 / ADR-0010

        hnsw = conn.execute(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE indexname = 'ix_document_chunks_embedding_hnsw'"
            )
        ).scalar()
        assert hnsw is not None and "hnsw" in hnsw and "vector_cosine_ops" in hnsw

        gin_am = conn.execute(
            text(
                "SELECT am.amname FROM pg_class c "
                "JOIN pg_am am ON am.oid = c.relam "
                "WHERE c.relname = 'ix_document_chunks_tsv'"
            )
        ).scalar()
        assert gin_am == "gin"  # CIT-002 keyword search


def test_no_float_money_columns(alembic_cfg: Config, test_engine: Engine) -> None:
    command.upgrade(alembic_cfg, "head")
    with test_engine.connect() as conn:
        floats = conn.execute(
            text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_schema = 'public' AND data_type IN ('double precision', 'real')"
            )
        ).scalar()
    assert floats == 0  # DB-003


def test_downgrade_leaves_empty_schema(alembic_cfg: Config, test_engine: Engine) -> None:
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "base")
    tables = public_table_names(test_engine)
    assert tables & _MODEL_TABLES == set()  # only alembic_version may remain


def test_up_down_up_on_populated_db(alembic_cfg: Config, test_engine: Engine) -> None:
    command.upgrade(alembic_cfg, "head")

    # Seed against the test engine directly (avoids app.db's cached dev-DB engine).
    seed = _seed_module()
    with Session(test_engine) as session:
        count = seed.seed_into(session)
        session.commit()
    assert count == 3  # NVDA, AAPL, JPM

    with test_engine.connect() as conn:
        companies = conn.execute(text("SELECT count(*) FROM companies")).scalar()
    assert companies == 3

    # Downgrade must succeed even with data present (FK cascades), then re-upgrade cleanly.
    command.downgrade(alembic_cfg, "base")
    assert public_table_names(test_engine) & _MODEL_TABLES == set()
    command.upgrade(alembic_cfg, "head")
    assert public_table_names(test_engine) >= _MODEL_TABLES
