"""Price ingestion integration tests (Phase 1d DoD). Mock source + test DB. Skips offline."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.ingestion.prices import ingest_prices
from app.ingestion.sec import ingest_company
from app.models import Company, CorporateAction, DataFreshness, PriceHistory
from app.providers.prices.mock import MockPriceSource
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
def nvda(session: Session, tmp_path: Path) -> Company:
    ingest_company(session, "NVDA", sec=MockSecSource(), storage=FilesystemObjectStorage(tmp_path))
    return session.scalars(select(Company).where(Company.ticker == "NVDA")).one()


def _count(session: Session, model: Any, company_id: int) -> int:
    return (
        session.scalar(
            select(func.count()).select_from(model).where(model.company_id == company_id)
        )
        or 0
    )


def test_price_history_has_five_years_with_raw_and_adjusted(
    session: Session, nvda: Company
) -> None:
    counts = ingest_prices(session, nvda, source=MockPriceSource())
    assert counts.bars > 1000  # ~5 years of daily bars (DoD #1)
    row = session.scalars(
        select(PriceHistory).where(PriceHistory.company_id == nvda.id).limit(1)
    ).one()
    assert row.close is not None and row.adj_close is not None  # both populated (DR-025)


def test_nvidia_2024_split_recorded(session: Session, nvda: Company) -> None:
    ingest_prices(session, nvda, source=MockPriceSource())
    split = session.scalars(
        select(CorporateAction).where(
            CorporateAction.company_id == nvda.id, CorporateAction.action_type == "split"
        )
    ).one()
    assert split.ratio_or_amount == Decimal("10")  # DoD #2
    assert split.ex_date is not None and split.ex_date.year == 2024

    # Raw close steps down ~10x across the split ex-date; adjusted stays continuous (DR-025).
    pre = session.scalars(
        select(PriceHistory)
        .where(PriceHistory.company_id == nvda.id, PriceHistory.date < split.ex_date)
        .order_by(PriceHistory.date.desc())
        .limit(1)
    ).one()
    post = session.scalars(
        select(PriceHistory)
        .where(PriceHistory.company_id == nvda.id, PriceHistory.date >= split.ex_date)
        .order_by(PriceHistory.date.asc())
        .limit(1)
    ).one()
    assert pre.close is not None and post.close is not None
    assert pre.close > post.close * 5  # raw dropped sharply
    assert pre.adj_close is not None and post.adj_close is not None
    assert abs(pre.adj_close - post.adj_close) < pre.adj_close  # adjusted continuous


def test_reingest_is_idempotent(session: Session, nvda: Company) -> None:
    ingest_prices(session, nvda, source=MockPriceSource())
    prices_1 = _count(session, PriceHistory, nvda.id)
    actions_1 = _count(session, CorporateAction, nvda.id)
    ingest_prices(session, nvda, source=MockPriceSource())
    assert _count(session, PriceHistory, nvda.id) == prices_1  # no duplicate bars (ING-001)
    assert _count(session, CorporateAction, nvda.id) == actions_1


def test_data_freshness_updated(session: Session, nvda: Company) -> None:
    ingest_prices(session, nvda, source=MockPriceSource())
    freshness = session.scalars(
        select(DataFreshness).where(
            DataFreshness.company_id == nvda.id, DataFreshness.source == "price"
        )
    ).one()
    assert freshness.status == "fresh"
    assert freshness.last_success_at is not None  # DoD #5


def test_dividends_recorded(session: Session, nvda: Company) -> None:
    ingest_prices(session, nvda, source=MockPriceSource())
    dividends = _count_actions(session, nvda.id, "dividend")
    assert dividends > 0  # quarterly dividends in the fixture


def _count_actions(session: Session, company_id: int, kind: str) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(CorporateAction)
            .where(CorporateAction.company_id == company_id, CorporateAction.action_type == kind)
        )
        or 0
    )
