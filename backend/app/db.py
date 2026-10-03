"""Database engine and session factory.

The engine is created lazily so importing the models (e.g. for Alembic autogenerate or a
test that builds its own engine) never opens a connection as a side effect.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy engine."""
    return create_engine(get_settings().database_url, pool_pre_ping=True, future=True)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session: commits on success, rolls back on error, always closes."""
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency: a read session that always closes (overridable in tests)."""
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()
