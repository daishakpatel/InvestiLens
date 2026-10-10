"""Phase 6a portfolio-analysis integration (§37.2): weighted metrics, concentration, price-based
risk, aggregated cited risk themes, and the endpoint.

Hand-seeds three companies with metrics, price series, and research reports so every path has data
(including the risk-theme aggregation that needs completed reports). Deterministic; non-advisory.

Refs: §37.2, DR-041 (metric N/A), LGL-006 (non-advice).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import app
from app.models import Company, FinancialMetric, PriceHistory, ResearchReport
from app.portfolio.analysis import analyze
from app.portfolio.themes import aggregate_themes
from app.portfolio.weights import normalize
from app.schemas.portfolio import Holding, PortfolioRequest

_TODAY = date(2026, 9, 30)
_METRICS = {
    "TCH1": {"gross_margin": "0.70", "net_margin": "0.50", "roe": "0.60", "debt_to_equity": "0.20"},
    "TCH2": {"gross_margin": "0.45", "net_margin": "0.12", "roe": "0.25", "debt_to_equity": "0.40"},
    # FIN1 is a "bank": no gross margin (N/A), to exercise partial-coverage weighting.
    "FIN1": {"net_margin": "0.30", "roe": "0.15", "debt_to_equity": "1.80"},
}
_SECTORS = {"TCH1": "Technology", "TCH2": "Technology", "FIN1": "Financials"}


@pytest.fixture(scope="module")
def _migrated(test_db_url: str) -> None:
    from tests.integration.conftest import _MIGRATIONS_DIR

    cfg = Config()
    cfg.set_main_option("script_location", _MIGRATIONS_DIR)
    cfg.set_main_option("sqlalchemy.url", test_db_url)
    command.upgrade(cfg, "head")


def _seed(session: Session) -> dict[str, int]:
    ids: dict[str, int] = {}
    for i, (ticker, sector) in enumerate(_SECTORS.items()):
        company = Company(ticker=ticker, cik=f"000000010{i}", name=f"{ticker} Inc.", sector=sector)
        session.add(company)
        session.flush()
        ids[ticker] = company.id
        for name, value in _METRICS[ticker].items():
            session.add(
                FinancialMetric(
                    company_id=company.id,
                    period="FY2025",
                    fiscal_year=2025,
                    period_type="FY",
                    metric_name=name,
                    metric_value=Decimal(value),
                    unit="ratio",
                    source_id=f"derived:{ticker}:{name}:FY2025",
                    is_derived=True,
                    is_latest=True,
                )
            )
        # A deterministic price series (distinct trend per holding) for volatility/correlation.
        for d in range(40):
            day = _TODAY - timedelta(days=39 - d)
            price = Decimal(100) + Decimal((i + 1) * (d % 5)) - Decimal(d % 3)
            session.add(PriceHistory(company_id=company.id, date=day, close=price, adj_close=price))
    # Completed reports with cited risks: TCH1 and TCH2 share a "supply_chain" theme.
    session.add(
        ResearchReport(
            company_id=ids["TCH1"],
            status="complete",
            report_json={
                "risks": [
                    {
                        "category": "supply_chain",
                        "description": "Foundry concentration.",
                        "source_ids": ["derived:TCH1:x:FY2025"],
                    },
                    {
                        "category": "competitive",
                        "description": "Rival accelerators.",
                        "source_ids": ["derived:TCH1:y:FY2025"],
                    },
                ]
            },
        )
    )
    session.add(
        ResearchReport(
            company_id=ids["TCH2"],
            status="complete",
            report_json={
                "risks": [
                    {
                        "category": "supply_chain",
                        "description": "Wafer supply limits.",
                        "source_ids": ["derived:TCH2:x:FY2025"],
                    },
                ]
            },
        )
    )
    session.flush()
    return ids


@pytest.fixture(scope="module")
def seeded(_migrated: None, test_db_url: str) -> Iterator[None]:
    from sqlalchemy import create_engine

    from tests.integration.conftest import truncate_all

    engine = create_engine(test_db_url, future=True)
    try:
        with Session(engine) as s:
            _seed(s)
            s.commit()
        yield
    finally:
        truncate_all(engine)  # committed seed data must not leak into the shared throwaway DB
        engine.dispose()


@pytest.fixture
def session(seeded: None, test_engine: Engine) -> Iterator[Session]:
    with Session(test_engine) as s:
        yield s
        s.rollback()


@pytest.fixture
def client(session: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(session, "commit", session.flush)
    app.dependency_overrides[get_db] = lambda: session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


_P = "/api/v1"


def _request() -> PortfolioRequest:
    return PortfolioRequest(
        holdings=[
            Holding(ticker="TCH1", weight=Decimal(40)),
            Holding(ticker="TCH2", weight=Decimal(30)),
            Holding(ticker="FIN1", weight=Decimal(30)),
        ]
    )


# --- deterministic aggregates (DoD #3) ----------------------------------------------------------


def test_portfolio_weighted_metrics_concentration_and_risk(session: Session) -> None:
    a = analyze(session, _request(), today=_TODAY)

    # Weights normalized to sum to 1.
    assert sum(h.weight for h in a.holdings) == Decimal(1)

    # HHI = 0.4² + 0.3² + 0.3² = 0.34.
    assert a.concentration is not None
    assert a.concentration.hhi == Decimal("0.34000000")
    assert a.concentration.top_holding == "TCH1"

    # Sector exposure: Technology 0.70, Financials 0.30.
    exposure = {e.sector: e.weight for e in a.sector_exposure}
    assert exposure["Technology"] == Decimal("0.70000000")
    assert exposure["Financials"] == Decimal("0.30000000")

    # gross_margin: FIN1 has none → coverage 0.70 of weight, renormalized over TCH1/TCH2 (DR-041).
    gm = next(m for m in a.weighted_metrics if m.metric_name == "gross_margin")
    assert gm.coverage == Decimal("0.70000000")
    assert gm.value is not None and gm.warnings == ["PARTIAL_COVERAGE"]

    # Price-based risk computed deterministically for all three holdings.
    assert a.risk_stats is not None
    assert a.risk_stats.portfolio_volatility is not None
    assert all(hv.annualized_volatility is not None for hv in a.risk_stats.holding_volatility)
    assert len(a.risk_stats.correlation) == 3


def test_holdings_data_supports_client_side_what_if(session: Session) -> None:
    # DoD #4: the response carries per-holding values + volatility so the client recomputes
    # weighted metrics / HHI / portfolio vol on a weight change without a backend round-trip.
    a = analyze(session, _request(), today=_TODAY)
    by_ticker = {h.ticker: h for h in a.holdings_data}
    assert set(by_ticker) == {"TCH1", "TCH2", "FIN1"}
    assert by_ticker["TCH1"].metrics["gross_margin"].value == Decimal("0.70")
    assert by_ticker["TCH1"].annualized_volatility is not None
    assert "gross_margin" not in by_ticker["FIN1"].metrics  # N/A not fabricated


# --- aggregated cited risk themes (DoD / §37.2 item 9) ------------------------------------------


def test_risk_themes_aggregate_and_stay_cited(session: Session) -> None:
    weights = normalize([Holding(ticker=t, weight=Decimal(1)) for t in ("TCH1", "TCH2", "FIN1")])
    themes, missing = aggregate_themes(session, weights)
    supply = next(t for t in themes if t.category == "supply_chain")
    assert supply.holding_count == 2  # shared by TCH1 and TCH2
    assert all(c.source_ids for c in supply.contributions)  # every contribution stays cited
    assert "FIN1" in missing  # no report → excluded, surfaced


# --- endpoint -----------------------------------------------------------------------------------


def test_portfolio_endpoint(client: TestClient) -> None:
    resp = client.post(
        f"{_P}/portfolio/analyze",
        json={
            "holdings": [
                {"ticker": "TCH1", "weight": "40"},
                {"ticker": "TCH2", "weight": "30"},
                {"ticker": "FIN1", "weight": "30"},
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["holdings"]) == 3
    assert body["concentration"]["hhi"] == "0.34000000"
    assert "not investment advice" in body["disclaimer"].lower()
    assert "rebalance" in body["disclaimer"].lower()  # explicit non-advice framing


def test_portfolio_unknown_ticker_is_422(client: TestClient) -> None:
    body = {"holdings": [{"ticker": "ZZZZ", "weight": "1"}]}
    resp = client.post(f"{_P}/portfolio/analyze", json=body)
    assert resp.status_code == 422
