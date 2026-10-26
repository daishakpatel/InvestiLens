"""Throwaway-database helpers shared by the eval report and the local demo build (Phase 7l)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse, urlunparse

_MIGRATIONS = Path(__file__).resolve().parents[1] / "infrastructure" / "migrations"


def with_database(url: str, name: str) -> str:
    """`url` with its database replaced by `name`."""
    return urlunparse(urlparse(url)._replace(path=f"/{name}"))


def _admin_dsn(url: str) -> str:
    return with_database(url, "postgres").replace("postgresql+psycopg://", "postgresql://")


def recreate_database(base_url: str, name: str) -> str:
    """Drop and create `name` on `base_url`'s server, migrate it to head; returns its URL."""
    import psycopg
    from alembic import command
    from alembic.config import Config

    with psycopg.connect(_admin_dsn(base_url), autocommit=True, connect_timeout=5) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{name}"')
    url = with_database(base_url, name)
    cfg = Config()
    cfg.set_main_option("script_location", str(_MIGRATIONS))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    return url


def drop_database(base_url: str, name: str) -> None:
    import psycopg

    with psycopg.connect(_admin_dsn(base_url), autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
