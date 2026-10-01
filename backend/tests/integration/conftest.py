"""Fixtures for integration tests that need a real PostgreSQL + pgvector.

A throwaway database is created for the test session and dropped afterwards, so tests never
touch the developer's working database. If no PostgreSQL server is reachable (e.g. `make check`
run offline), these tests skip rather than fail — the unit suite stays fully offline, while CI
provides a Postgres service so the migration tests always run there.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from urllib.parse import urlparse, urlunparse

import psycopg
import pytest
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text

from app.config import get_settings

_MIGRATIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "infrastructure", "migrations"
)
_TEST_DB_NAME = "investilens_test"


def _server_url(db_url: str, database: str) -> str:
    """Return `db_url` with its database (path) replaced by `database`."""
    parts = urlparse(db_url)
    return urlunparse(parts._replace(path=f"/{database}"))


def _psycopg_dsn(sqlalchemy_url: str) -> str:
    """Convert a `postgresql+psycopg://` URL to a plain libpq DSN."""
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://")


@pytest.fixture(scope="session")
def test_db_url() -> Iterator[str]:
    """Create an empty test database for the session; drop it at the end."""
    base = os.environ.get("TEST_DATABASE_URL", get_settings().database_url)
    admin_dsn = _psycopg_dsn(_server_url(base, "postgres"))
    test_url = _server_url(base, _TEST_DB_NAME)

    try:
        admin = psycopg.connect(admin_dsn, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as exc:  # no server reachable
        pytest.skip(f"PostgreSQL not reachable for integration tests: {exc}")

    with admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{_TEST_DB_NAME}" WITH (FORCE)')
        admin.execute(f'CREATE DATABASE "{_TEST_DB_NAME}"')
    try:
        yield test_url
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{_TEST_DB_NAME}" WITH (FORCE)')


@pytest.fixture
def alembic_cfg(test_db_url: str) -> Config:
    """An Alembic config pointed at the throwaway test database."""
    cfg = Config()
    cfg.set_main_option("script_location", _MIGRATIONS_DIR)
    cfg.set_main_option("sqlalchemy.url", test_db_url)
    return cfg


@pytest.fixture
def test_engine(test_db_url: str) -> Iterator[Engine]:
    engine = create_engine(test_db_url, future=True)
    try:
        yield engine
    finally:
        engine.dispose()


def public_table_names(engine: Engine) -> set[str]:
    """Return the base table names in the public schema."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )
        )
        return {r[0] for r in rows}
