"""Phase 1c ratio-builder integration: persist derived ratios, golden match, N/A handling."""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.finance.builder import build_company_metrics
from app.finance.ratio_builder import build_company_ratios
from app.ingestion.sec import ingest_company
from app.models import Company, FinancialMetric
from app.providers.sec.mock import MockSecSource
from app.utils.storage import FilesystemObjectStorage

_GOLDEN = {
    c["ticker"]: c
    for c in json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "golden_metrics.json").read_text()
    )["companies"]
}


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


def _prepare(session: Session, ticker: str, tmp_path: Path) -> Company:
    ingest_company(session, ticker, sec=MockSecSource(), storage=FilesystemObjectStorage(tmp_path))
    company = session.scalars(select(Company).where(Company.ticker == ticker)).one()
    build_company_metrics(session, company)
    build_company_ratios(session, company)
    return company


def _latest_fy(session: Session, company: Company) -> int:
    return int(
        session.scalar(
            select(func.max(FinancialMetric.fiscal_year)).where(
                FinancialMetric.company_id == company.id,
                FinancialMetric.metric_name == "revenue",
                FinancialMetric.period_type == "FY",
            )
        )
    )


def _derived(session: Session, company: Company, metric: str, fy: int) -> FinancialMetric | None:
    return session.scalars(
        select(FinancialMetric).where(
            FinancialMetric.company_id == company.id,
            FinancialMetric.metric_name == metric,
            FinancialMetric.fiscal_year == fy,
            FinancialMetric.is_derived.is_(True),
        )
    ).first()


def test_gross_margin_persisted_matches_golden(session: Session, tmp_path: Path) -> None:
    for ticker in ("NVDA", "AAPL"):
        company = _prepare(session, ticker, tmp_path / ticker)
        fy = _latest_fy(session, company)
        gm = _derived(session, company, "gross_margin", fy)
        assert gm is not None and gm.metric_value is not None
        golden = _GOLDEN[ticker]["metrics"]["gross_margin"]["value"]
        assert gm.metric_value.quantize(Decimal("0.0001")) == Decimal(golden)


def test_jpm_gross_margin_is_null_with_reason(session: Session, tmp_path: Path) -> None:
    company = _prepare(session, "JPM", tmp_path / "JPM")
    fy = _latest_fy(session, company)
    gm = _derived(session, company, "gross_margin", fy)
    assert gm is not None
    assert gm.metric_value is None  # not zero, not missing
    assert gm.quality_flags is not None
    assert gm.quality_flags["warnings"] == ["NOT_APPLICABLE_SECTOR"]  # with a reason


def test_derived_metric_has_lineage(session: Session, tmp_path: Path) -> None:
    company = _prepare(session, "NVDA", tmp_path / "NVDA")
    fy = _latest_fy(session, company)
    nm = _derived(session, company, "net_margin", fy)
    assert nm is not None and nm.quality_flags is not None
    inputs = nm.quality_flags["inputs"]
    assert {i["name"] for i in inputs} == {"net_income", "revenue"}
    assert all(i["source_id"] for i in inputs)  # traceable back to the source facts


def test_rebuild_is_idempotent(session: Session, tmp_path: Path) -> None:
    company = _prepare(session, "NVDA", tmp_path / "NVDA")
    first = session.scalar(
        select(func.count())
        .select_from(FinancialMetric)
        .where(FinancialMetric.company_id == company.id, FinancialMetric.is_derived.is_(True))
    )
    build_company_ratios(session, company)
    second = session.scalar(
        select(func.count())
        .select_from(FinancialMetric)
        .where(FinancialMetric.company_id == company.id, FinancialMetric.is_derived.is_(True))
    )
    assert first is not None and first == second and first > 0
