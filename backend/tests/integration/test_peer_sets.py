"""Peer sets, valuation history and valuation bands (Phase 7h). Real Postgres, mock SEC + prices.

Requirement IDs: FR-PS-001/002/003/004/008/009/010/012, DR-PS-001/002/003.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.citation.resolver import resolve_source
from app.comparison.peers import default_peers, refresh_default_peer_set
from app.db import get_db
from app.finance.builder import build_company_metrics
from app.finance.ratio_builder import build_company_ratios
from app.finance.valuation_history import build_valuation_history
from app.ingestion.prices import ingest_prices
from app.ingestion.sec import ingest_company
from app.main import app
from app.models import Company, User, ValuationHistory
from app.providers.prices.mock import MockPriceSource
from app.providers.sec.mock import MockSecSource
from app.repositories import metrics as metrics_repo
from app.utils.storage import FilesystemObjectStorage
from tests.fakes import auth_headers

_P = "/api/v1"
X = "\u00d7"  # the times sign in rationales


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
def client(session: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(session, "commit", session.flush)
    app.dependency_overrides[get_db] = lambda: session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _company(
    session: Session, ticker: str, sic: str, cap: int | None, unit: str = "USD"
) -> Company:
    company = Company(
        ticker=ticker, cik=f"{abs(hash(ticker)) % 10**10:010d}", name=f"{ticker} Inc", sic_code=sic
    )
    session.add(company)
    session.flush()
    if cap is not None:
        metrics_repo.upsert_metric(
            session,
            company_id=company.id,
            period="2026-09-30",
            fiscal_year=2026,
            fiscal_quarter=None,
            period_start=None,
            period_end=date(2026, 9, 30),
            period_type="LATEST",
            metric_name="market_cap",
            metric_value=Decimal(cap),
            unit=unit,
            is_derived=True,
            source_id=f"derived:{ticker}:market_cap:2026-09-30",
            as_reported_accession="derived",
        )
    return company


def _universe(session: Session) -> Company:
    """A target (cap 100) and candidates around it, to exercise every part of the rule."""
    target = _company(session, "TGT", "3674", 100)
    _company(session, "NEAR", "3674", 120)  # 1.2x: in
    _company(session, "HALF", "3674", 50)  # 0.5x: in
    _company(session, "TWICE", "3674", 200)  # 2.0x: in, as far as HALF on a log scale
    _company(session, "EDGE", "3674", 400)  # 4.0x: in (band is inclusive)
    _company(session, "HUGE", "3674", 500)  # 5.0x: out of band
    _company(session, "TINY", "3674", 20)  # 0.2x: out of band
    _company(session, "OTHER", "3571", 100)  # different SIC
    _company(session, "EURO", "3674", 100, unit="EUR")  # different currency
    _company(session, "NOCAP", "3674", None)  # no market cap
    return target


def test_default_peers_follow_the_rule_and_are_deterministic(session: Session) -> None:
    target = _universe(session)
    peers = default_peers(session, target)
    assert [(c.ticker, why) for c, why in peers] == [
        ("NEAR", f"same SIC 3674; market cap 1.2{X} target"),
        ("HALF", f"same SIC 3674; market cap 0.5{X} target"),
        ("TWICE", f"same SIC 3674; market cap 2.0{X} target"),
        ("EDGE", f"same SIC 3674; market cap 4.0{X} target"),
    ]
    first = refresh_default_peer_set(session, target)
    second = refresh_default_peer_set(session, target)  # same data, same set, same row
    assert first.id == second.id
    assert [c.ticker for c, _ in default_peers(session, target)] == [c.ticker for c, _ in peers]


def test_too_few_candidates_is_insufficient(session: Session, client: TestClient) -> None:
    lone = _company(session, "LONE", "1311", 100)
    _company(session, "PAIR", "1311", 110)
    refresh_default_peer_set(session, lone)
    body = client.get(f"{_P}/companies/LONE/peer-sets").json()
    (default,) = body["peer_sets"]
    assert default["kind"] == "system_default" and default["insufficient"]
    assert default["members"][0]["rationale"] == f"same SIC 1311; market cap 1.1{X} target"
    assert default["reason"].startswith("Insufficient peers: 1 other company in Assay Desk shares")
    no_sic = _company(session, "NOSIC", "", 100)
    assert default_peers(session, no_sic) == []


def _users(session: Session) -> tuple[User, User]:
    owner = User(email="peers@example.com", password_hash="x")  # noqa: S106
    other = User(email="other@example.com", password_hash="x")  # noqa: S106
    session.add_all([owner, other])
    session.flush()
    return owner, other


def test_user_sets_are_private_validated_and_editable(session: Session, client: TestClient) -> None:
    _universe(session)
    owner, other = _users(session)
    mine, theirs = auth_headers(owner.id), auth_headers(other.id)
    created = client.post(
        f"{_P}/companies/TGT/peer-sets",
        json={"name": "Chip peers", "tickers": ["near", "OTHER"]},
        headers=mine,
    )
    assert created.status_code == 201
    set_id = created.json()["id"]
    assert [m["ticker"] for m in created.json()["members"]] == ["NEAR", "OTHER"]
    assert created.json()["members"][0]["rationale"] == "chosen by you"

    # Private: invisible and unchangeable to anyone else (404, never 403).
    assert client.get(f"{_P}/companies/TGT/peer-sets", headers=theirs).json()["peer_sets"] == []
    assert (
        client.patch(
            f"{_P}/companies/TGT/peer-sets/{set_id}", json={"name": "x"}, headers=theirs
        ).status_code
        == 404
    )
    assert client.get(f"{_P}/companies/TGT/valuation-bands?peer_set_id={set_id}").status_code == 404
    assert (
        client.get(
            f"{_P}/companies/TGT/valuation-bands?peer_set_id={set_id}", headers=mine
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"{_P}/companies/TGT/peer-sets", json={"name": "x", "tickers": ["NEAR"]}
        ).status_code
        == 401
    )

    unknown = client.post(
        f"{_P}/companies/TGT/peer-sets",
        json={"name": "x", "tickers": ["NEAR", "ZZZZ"]},
        headers=mine,
    )
    assert unknown.status_code == 422
    assert (
        "Not in Assay Desk yet: ZZZZ. Add this company to your watchlist first"
        in unknown.json()["title"]
    )
    itself = client.post(
        f"{_P}/companies/TGT/peer-sets", json={"name": "x", "tickers": ["TGT"]}, headers=mine
    )
    assert itself.status_code == 422 and "its own peer" in itself.json()["title"]
    too_many = [f"T{i}" for i in range(13)]
    assert (
        client.post(
            f"{_P}/companies/TGT/peer-sets", json={"name": "x", "tickers": too_many}, headers=mine
        ).status_code
        == 422
    )

    renamed = client.patch(
        f"{_P}/companies/TGT/peer-sets/{set_id}",
        json={"tickers": ["HALF", "TWICE", "EDGE"]},
        headers=mine,
    ).json()
    assert renamed["name"] == "Chip peers" and [m["ticker"] for m in renamed["members"]] == [
        "HALF",
        "TWICE",
        "EDGE",
    ]
    assert not renamed["insufficient"]
    only_name = client.patch(
        f"{_P}/companies/TGT/peer-sets/{set_id}", json={"name": "Renamed"}, headers=mine
    ).json()
    assert only_name["name"] == "Renamed" and len(only_name["members"]) == 3
    bad = client.patch(
        f"{_P}/companies/TGT/peer-sets/{set_id}", json={"tickers": ["ZZZZ"]}, headers=mine
    )
    assert bad.status_code == 422

    refresh_default_peer_set(
        session, session.scalars(select(Company).where(Company.ticker == "TGT")).one()
    )
    default_id = next(
        s["id"] for s in client.get(f"{_P}/companies/TGT/peer-sets").json()["peer_sets"]
    )
    assert (
        client.delete(f"{_P}/companies/TGT/peer-sets/{default_id}", headers=mine).status_code == 404
    )
    assert client.delete(f"{_P}/companies/TGT/peer-sets/{set_id}", headers=mine).status_code == 204
    assert client.delete(f"{_P}/companies/TGT/peer-sets/{set_id}", headers=mine).status_code == 404
    assert (
        client.get(f"{_P}/companies/TGT/peer-sets", headers=mine).json()["peer_sets"][0]["kind"]
        == "system_default"
    )


def _priced(session: Session, ticker: str, tmp_path: Path) -> Company:
    ingest_company(session, ticker, sec=MockSecSource(), storage=FilesystemObjectStorage(tmp_path))
    company = session.scalars(select(Company).where(Company.ticker == ticker)).one()
    build_company_metrics(session, company)
    build_company_ratios(session, company)
    ingest_prices(session, company, source=MockPriceSource())  # also rebuilds the history
    return company


def test_nvda_history_is_point_in_time_and_cited(session: Session, tmp_path: Path) -> None:
    nvda = _priced(session, "NVDA", tmp_path)
    rows = list(
        session.scalars(select(ValuationHistory).where(ValuationHistory.company_id == nvda.id))
    )
    dates = sorted({(r.as_of_date, r.kind) for r in rows})
    assert [k for _, k in dates].count("fiscal_year_end") == 5 and dates[-1][1] == "current"
    assert len(rows) == 6 * 8
    year_end = next(
        r
        for r in rows
        if r.kind == "fiscal_year_end" and r.multiple == "pe_ratio" and r.fiscal_year == 2026
    )
    # At the FY2026 year end (2026-01-25) the 10-K was not filed yet: TTM runs to Q3.
    assert year_end.inputs["quarter_end"] == "2025-10-26"
    revenue = next(f for f in year_end.inputs["figures"] if f["name"] == "revenue")
    assert all(resolve_source(session, sid) is not None for sid in revenue["source_ids"])
    assert year_end.inputs["price"]["source_id"].startswith("price:NVDA:")
    assert resolve_source(session, year_end.inputs["shares"]["source_id"]) is not None
    # Rebuilding replaces the history.
    assert build_valuation_history(session, nvda) == len(rows)


def test_a_company_without_prices_has_no_history(session: Session, tmp_path: Path) -> None:
    ingest_company(session, "JPM", sec=MockSecSource(), storage=FilesystemObjectStorage(tmp_path))
    jpm = session.scalars(select(Company).where(Company.ticker == "JPM")).one()
    assert build_valuation_history(session, jpm) == 0


def _history(session: Session, company: Company, value: str | None, status: str = "ok") -> None:
    session.add(
        ValuationHistory(
            company_id=company.id,
            as_of_date=date(2026, 9, 30),
            kind="current",
            multiple="pe_ratio",
            value=Decimal(value) if value else None,
            status=status,
            inputs={},
        )
    )


def test_valuation_bands_endpoint(session: Session, client: TestClient, tmp_path: Path) -> None:
    _priced(session, "NVDA", tmp_path)
    owner, _ = _users(session)
    peers = [_company(session, t, "9999", None) for t in ("PA", "PB", "PC", "PD")]
    for peer, value in zip(peers[:3], ("20", "30", "40"), strict=True):
        _history(session, peer, value)
    _history(session, peers[3], None, "missing_input")  # e.g. fewer than four quarters
    session.flush()

    default = client.get(f"{_P}/companies/NVDA/valuation-bands").json()
    assert default["as_of"] == "2026-09-30" and default["peer_set"]["insufficient"]
    pe = next(b for b in default["bands"] if b["multiple"] == "pe_ratio")
    assert pe["unit"] == "x" and len(pe["history"]) == 6
    assert pe["peers"]["reason"].startswith("Insufficient peers")
    assert pe["own"]["n"] >= 1

    created = client.post(
        f"{_P}/companies/NVDA/peer-sets",
        json={"name": "Test peers", "tickers": ["PA", "PB", "PC", "PD"]},
        headers=auth_headers(owner.id),
    ).json()
    body = client.get(
        f"{_P}/companies/NVDA/valuation-bands?peer_set_id={created['id']}",
        headers=auth_headers(owner.id),
    ).json()
    pe = next(b for b in body["bands"] if b["multiple"] == "pe_ratio")
    assert pe["peers"]["n"] == 3 and pe["peers"]["median"] == "30.00000000"
    assert pe["peers"]["excluded"] == [
        {
            "ticker": "PD",
            "reason": "Not available: a price, share count or four quarters of figures is missing.",
        }
    ]
    if pe["value"] is not None:
        assert pe["peers"]["label"].endswith("peer median")
    ps = next(b for b in body["bands"] if b["multiple"] == "ps_ratio")
    assert ps["peers"]["n"] == 0 and len(ps["peers"]["excluded"]) == 4  # no peer history for P/S

    compared = client.get(
        f"{_P}/compare?peer_set_id={created['id']}", headers=auth_headers(owner.id)
    ).json()
    assert [c["ticker"] for c in compared["companies"]] == ["NVDA", "PA", "PB", "PC", "PD"]
    assert client.get(f"{_P}/compare?peer_set_id={created['id']}").status_code == 404  # private
    assert client.get(f"{_P}/compare").status_code == 422


def test_empty_peer_set_cannot_be_compared(session: Session, client: TestClient) -> None:
    target = _company(session, "SOLO", "4444", 100)
    default = refresh_default_peer_set(session, target)
    response = client.get(f"{_P}/compare?peer_set_id={default.id}")
    assert response.status_code == 422 and response.json()["title"] == "the peer set has no members"
