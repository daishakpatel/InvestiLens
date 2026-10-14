"""Phase 1b builder integration: persist canonical metrics from ingested facts.

Ingests NVDA (mock) then builds metrics against the throwaway test DB. Verifies golden match,
Q4 persistence, fiscal calendar, idempotency, and that an injected bad-unit fact is dead-lettered
into data_quality_issues. Skips offline (no DB).
"""

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

from app.citation.resolver import resolve_source
from app.finance.builder import build_company_metrics
from app.finance.ratio_builder import build_company_ratios
from app.ingestion.sec import ingest_company
from app.models import Company, DataQualityIssue, FinancialMetric, FiscalCalendar
from app.providers.sec.mock import MockSecSource
from app.repositories import quality as quality_repo
from app.schemas.sources import DerivedMetricSource, XbrlFactSource
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


@pytest.fixture
def nvda(session: Session, tmp_path: Path) -> Company:
    ingest_company(session, "NVDA", sec=MockSecSource(), storage=FilesystemObjectStorage(tmp_path))
    return session.scalars(select(Company).where(Company.ticker == "NVDA")).one()


def test_builder_persists_golden_revenue(session: Session, nvda: Company) -> None:
    build_company_metrics(session, nvda)
    latest = session.scalars(
        select(FinancialMetric)
        .where(
            FinancialMetric.company_id == nvda.id,
            FinancialMetric.metric_name == "revenue",
            FinancialMetric.period_type == "FY",  # annual, not the derived Q4 (same period_end)
            FinancialMetric.is_latest.is_(True),
        )
        .order_by(FinancialMetric.period_end.desc())
    ).first()
    assert latest is not None
    assert latest.metric_value == Decimal(_GOLDEN["NVDA"]["metrics"]["revenue"]["value"])
    assert latest.source_tag == "us-gaap:Revenues"


def test_every_latest_metric_has_its_own_source_id(session: Session, nvda: Company) -> None:
    # CIT-001, CIT-002: a source ID names exactly one metric. Base metrics used to share their
    # filing's accession number, so a net income question, and the citation behind it, resolved to
    # whichever metric of that filing came first (revenue).
    build_company_metrics(session, nvda)
    build_company_ratios(session, nvda)
    latest = session.scalars(
        select(FinancialMetric).where(
            FinancialMetric.company_id == nvda.id, FinancialMetric.is_latest.is_(True)
        )
    ).all()
    ids = [m.source_id for m in latest]
    assert len(ids) == len(set(ids)), "two metrics share a source ID"
    assert all(i and ":NVDA:" in i for i in ids), "IDs must be company-scoped"

    for name in ("net_income", "operating_income", "revenue"):
        row = max(
            (m for m in latest if m.metric_name == name and m.period_type == "FY"),
            key=lambda m: m.fiscal_year or 0,
        )
        detail = resolve_source(session, row.source_id or "")
        assert detail is not None
        source = detail.source
        assert isinstance(source, XbrlFactSource)
        assert (source.concept_tag, source.value) == (name, row.metric_value)
        assert source.accession_number == row.as_reported_accession  # the filing is still cited


def test_derived_quarter_cites_the_figures_it_came_from(session: Session, nvda: Company) -> None:
    # CIT-003, DR-022: Q4 = FY - (Q1+Q2+Q3). Its source must resolve with that lineage: the annual
    # figure by its own source ID, the three quarters by the filings they were reported in. The
    # inputs used to be bare accession strings, which the resolver could not read (HTTP 500).
    build_company_metrics(session, nvda)
    q4 = session.scalars(
        select(FinancialMetric)
        .where(
            FinancialMetric.company_id == nvda.id,
            FinancialMetric.metric_name == "revenue",
            FinancialMetric.fiscal_quarter == 4,
        )
        .order_by(FinancialMetric.fiscal_year.desc())
    ).first()
    assert q4 is not None and q4.source_id == f"derived:NVDA:revenue:Q4-FY{q4.fiscal_year}"

    detail = resolve_source(session, q4.source_id)
    assert detail is not None and isinstance(detail.source, DerivedMetricSource)
    assert detail.source.input_source_ids == [f"xbrl:NVDA:revenue:FY{q4.fiscal_year}"]
    assert [i["name"] for i in detail.lineage] == [f"FY{q4.fiscal_year}", "Q1", "Q2", "Q3"]
    assert all(i["accession"] for i in detail.lineage)
    annual = resolve_source(session, detail.source.input_source_ids[0])
    assert annual is not None and annual.source.source_id == detail.source.input_source_ids[0]


def test_builder_persists_derived_q4_and_fiscal_calendar(session: Session, nvda: Company) -> None:
    build_company_metrics(session, nvda)
    q4 = session.scalars(
        select(FinancialMetric).where(
            FinancialMetric.company_id == nvda.id,
            FinancialMetric.metric_name == "revenue",
            FinancialMetric.is_derived.is_(True),
            FinancialMetric.fiscal_quarter == 4,
        )
    ).first()
    assert q4 is not None and q4.metric_value is not None and q4.metric_value > 0
    assert q4.quality_flags is not None and len(q4.quality_flags["inputs"]) == 4  # lineage

    fy = session.scalars(
        select(FiscalCalendar)
        .where(FiscalCalendar.company_id == nvda.id, FiscalCalendar.period_type == "FY")
        .order_by(FiscalCalendar.period_end.desc())
    ).first()
    assert fy is not None and fy.period_end.month == 1 and fy.period_end.weekday() == 6


def test_rebuild_is_idempotent(session: Session, nvda: Company) -> None:
    build_company_metrics(session, nvda)
    first = session.scalar(
        select(func.count())
        .select_from(FinancialMetric)
        .where(FinancialMetric.company_id == nvda.id)
    )
    build_company_metrics(session, nvda)
    second = session.scalar(
        select(func.count())
        .select_from(FinancialMetric)
        .where(FinancialMetric.company_id == nvda.id)
    )
    assert first is not None and first == second and first > 0


def test_bad_unit_fact_goes_to_data_quality_issues(session: Session, nvda: Company) -> None:
    quality_repo.record_issue(
        session,
        company_id=nvda.id,
        metric_name="eps_diluted",
        period="FY2026",
        issue_code="UNIT_MISMATCH",
        details={"unit": "USD", "expected_family": "per_share"},
    )
    session.flush()
    issue = session.scalars(
        select(DataQualityIssue).where(DataQualityIssue.company_id == nvda.id)
    ).first()
    assert issue is not None and issue.issue_code == "UNIT_MISMATCH"


def test_quality_issues_recorded_for_bad_unit_and_negative_revenue(
    session: Session, tmp_path: Path
) -> None:
    """A bad-unit eps fact and a negative revenue flow into data_quality_issues (DR-024/028)."""
    from datetime import date

    from app.models import Company as _Company
    from app.models import DataQualityIssue, FinancialFact

    company = _Company(ticker="TST", cik="0000000001", name="Test Co", sector="Technology")
    session.add(company)
    session.flush()
    # Full fiscal year ending 2025-12-31; revenue negative (impossible), eps unit wrong.
    common = dict(
        company_id=company.id,
        accession_number="t-10k",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
        period_type="duration",
        filed_date=date(2026, 2, 1),
        is_amended=False,
    )
    session.add_all(
        [
            FinancialFact(
                concept_tag="us-gaap:Revenues", value=Decimal("-100"), unit="USD", **common
            ),
            FinancialFact(
                concept_tag="us-gaap:EarningsPerShareDiluted",
                value=Decimal("5"),
                unit="USD",
                **common,
            ),  # wrong unit (should be USD/shares)
        ]
    )
    session.flush()

    build_company_metrics(session, company)
    issues = {
        i.issue_code
        for i in session.scalars(
            select(DataQualityIssue).where(DataQualityIssue.company_id == company.id)
        )
    }
    assert "NEGATIVE_VALUE" in issues  # revenue < 0
    assert "UNIT_MISMATCH" in issues  # eps_diluted in USD, not USD/shares
