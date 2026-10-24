"""Governance persistence and endpoints (Phase 7g). Real Postgres, mock SEC, real proxy fixtures.

Requirement IDs: FR-GV-002/003/004/005/006/010/011, DR-GV-001/002/003.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.citation.resolver import resolve_source
from app.db import get_db
from app.governance import facts as tier_c
from app.governance.builder import build_company_governance, build_proxy
from app.ingestion.documents.pipeline import parse_and_chunk, parse_company_documents
from app.ingestion.sec import ingest_company
from app.main import app
from app.models import Company, Document, ExecCompFact, Filing
from app.providers.base import LLMClient
from app.providers.mocks._fixtures import fixture_gzip_bytes
from app.providers.sec.mock import MockSecSource
from app.utils.storage import FilesystemObjectStorage

_PROXIES = ("DEF 14A", "DEFA14A")


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


def _company(session: Session, ticker: str, storage: FilesystemObjectStorage) -> Company:
    ingest_company(session, ticker, sec=MockSecSource(), storage=storage)
    company = session.scalars(select(Company).where(Company.ticker == ticker)).one()
    parse_company_documents(session, company.id, storage=storage, filing_types=_PROXIES)
    return company


def _add_proxy(
    session: Session,
    company: Company,
    storage: FilesystemObjectStorage,
    html: str,
    *,
    accession: str,
    filed: date,
) -> Filing:
    """A proxy the mock manifest does not list (JPMorgan's, or a synthetic one), parsed."""
    key = storage.put(f"test/{accession}.htm", html.encode())
    document = Document(
        company_id=company.id, document_type="filing", source_tier=1, content_hash=accession
    )
    session.add(document)
    session.flush()
    filing = Filing(
        document_id=document.id,
        company_id=company.id,
        filing_type="DEF 14A",
        filing_date=filed,
        accession_number=accession,
        raw_document_location=key,
    )
    session.add(filing)
    session.flush()
    parse_and_chunk(session, filing, storage=storage)
    return filing


def _facts(session: Session, document_id: int) -> list[ExecCompFact]:
    return list(
        session.scalars(select(ExecCompFact).where(ExecCompFact.document_id == document_id))
    )


def _nvda(session: Session, tmp_path: Path) -> tuple[Company, Filing, Document]:
    storage = FilesystemObjectStorage(tmp_path)
    company = _company(session, "NVDA", storage)
    counts = build_company_governance(session, company, read_raw=storage.get)
    assert counts.proxies == 1  # the DEFA14A has no compensation table: stored, not extracted
    filing = session.scalars(
        select(Filing).where(Filing.company_id == company.id, Filing.filing_type == "DEF 14A")
    ).one()
    document = session.get(Document, filing.document_id)
    assert document is not None
    return company, filing, document


def test_nvda_proxy_persists_tiers_a_and_b(session: Session, tmp_path: Path) -> None:
    _, _, document = _nvda(session, tmp_path)
    info = (document.doc_metadata or {})["proxy"]
    assert (info["fiscal_year"], info["fiscal_year_source"]) == (
        2026,
        "pay_versus_performance_xbrl",
    )
    assert info["company_selected_measure"]  # ecd:CoSelectedMeasureName, as tagged
    rows = _facts(session, document.id)

    pvp = {(r.fiscal_year, r.fact_key): r for r in rows if r.tier == "pvp"}
    peo = pvp[(2026, "peo_total_comp")]
    assert peo.value == Decimal(36_343_830) and peo.source_id.startswith("xbrl:")
    assert {y for y, _ in pvp} == {2022, 2023, 2024, 2025, 2026}
    assert pvp[(2026, "tsr")].unit == "index"
    detail = resolve_source(session, peo.source_id)
    assert detail is not None and "ecd:PeoTotalCompAmt" in (detail.text or "")

    sct = [r for r in rows if r.tier == "sct" and r.role == "peo" and r.fact_key == "total"]
    assert sorted((r.fiscal_year, r.value) for r in sct) == [
        (2024, Decimal(34_167_902)),
        (2025, Decimal(49_866_251)),
        (2026, Decimal(36_343_830)),
    ]
    table = resolve_source(session, sct[0].source_id)
    assert table is not None and table.source.source_type == "table_chunk"

    ratio = {r.fact_key: r for r in rows if r.tier == "pay_ratio"}
    assert (ratio["ratio"].value, ratio["median_pay"].value) == (Decimal(129), Decimal(282_050))
    assert resolve_source(session, ratio["ratio"].source_id) is not None


def test_rebuilding_is_idempotent(session: Session, tmp_path: Path) -> None:
    company, _, document = _nvda(session, tmp_path)
    before = len(_facts(session, document.id))
    build_company_governance(session, company, read_raw=FilesystemObjectStorage(tmp_path).get)
    assert len(_facts(session, document.id)) == before


def test_proxy_fiscal_year_is_not_the_filing_year(session: Session, tmp_path: Path) -> None:
    """JPMorgan filed in April 2026; the proxy covers fiscal 2025 (DR-GV-002)."""
    storage = FilesystemObjectStorage(tmp_path)
    company = _company(session, "JPM", storage)
    html = fixture_gzip_bytes("jpm", "def14a.htm.gz").decode("utf-8", "ignore")
    filing = _add_proxy(
        session, company, storage, html, accession="0000019617-26-000096", filed=date(2026, 4, 6)
    )
    build_company_governance(session, company, read_raw=storage.get)
    document = session.get(Document, filing.document_id)
    assert document is not None and (document.doc_metadata or {})["proxy"]["fiscal_year"] == 2025
    rows = _facts(session, document.id)
    peo = next(
        r
        for r in rows
        if r.tier == "pvp" and r.fiscal_year == 2025 and r.fact_key == "peo_total_comp"
    )
    assert peo.value == Decimal(40_632_724) and peo.source_id.startswith("xbrl:")  # companyfacts


def test_corrupted_row_is_rejected_and_logged(
    session: Session, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, filing, document = _nvda(session, tmp_path)
    html = fixture_gzip_bytes("nvda", "def14a.htm.gz").decode("utf-8", "ignore")
    _, rejected = build_proxy(session, filing, document, html.replace("24,800,511", "24,800,911"))
    assert rejected == 1
    assert "governance.sct_row_rejected" in capsys.readouterr().out
    rows = _facts(session, document.id)
    assert not any(r.tier == "sct" and r.role == "peo" and r.fiscal_year == 2026 for r in rows)
    # With the CEO's 2026 row gone there is no validated total to check the ratio against.
    assert not any(r.tier == "pay_ratio" for r in rows)
    assert (document.doc_metadata or {})["proxy"]["pay_ratio_status"] == "no_ceo_total"


_SYNTHETIC = """<html><body>
<p>Board of Directors</p><p>Our Board currently consists of nine members.</p>
<p>Summary Compensation Table</p>
<table>
<tr><td>Name and Principal Position</td><td>Year</td><td>Salary ($)</td><td>Total ($)</td></tr>
<tr><td>Pat Example, Chief Executive Officer</td><td>2024</td><td>1,000,000</td>
<td>1,000,000</td></tr>
</table></body></html>"""


def test_proxy_without_pvp_says_why(session: Session, client: TestClient, tmp_path: Path) -> None:
    """No Pay Versus Performance XBRL: the year comes from the table and PvP is an explicit
    null with a reason, never zeros (FR-GV-004)."""
    storage = FilesystemObjectStorage(tmp_path)
    company = _company(session, "AAPL", storage)
    _add_proxy(
        session, company, storage, _SYNTHETIC, accession="synthetic-proxy", filed=date(2025, 1, 10)
    )
    build_company_governance(session, company, read_raw=storage.get)
    body = client.get("/api/v1/companies/AAPL/governance").json()
    assert (body["fiscal_year"], body["fiscal_year_source"]) == (2024, "summary_compensation_table")
    assert body["pay_vs_performance"] == {
        "points": [],
        "company_selected_measure": None,
        "reason": "This proxy has no Pay Versus Performance XBRL facts.",
    }
    assert body["pay_ratio"]["ratio"] is None and "within 2%" in body["pay_ratio"]["reason"]
    assert body["compensation"]["rows"][0]["total"] == "1000000.00000000"
    assert body["coverage"]["summary_compensation_table"] and not body["coverage"]["pay_ratio"]


class _Recorded(LLMClient):
    """Answers with the board size, quoting the shown paragraph that states it."""

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, messages: Any, *, model: str, max_tokens: int) -> str:
        raise NotImplementedError

    async def complete_json(
        self, messages: Any, *, model: str, schema: dict[str, Any], max_tokens: int
    ) -> dict[str, Any]:
        self.calls += 1
        user = messages[1].content
        pid = user.split("Our Board currently consists of 10 members")[0].rsplit(
            "[paragraph_id=", 1
        )[1]
        pid = pid.split("]", 1)[0]
        quote = "Our Board currently consists of 10 members"
        return {"fields": {"board_size": {"value": 10, "quote": quote, "paragraph_id": pid}}}


def test_governance_endpoints(session: Session, client: TestClient, tmp_path: Path) -> None:
    _, _, document = _nvda(session, tmp_path)
    body = client.get("/api/v1/companies/NVDA/governance").json()
    assert body["fiscal_year"] == 2026 and body["filing"]["filing_type"] == "DEF 14A"
    assert body["proxies_ingested"] == 1 and body["available_years"] == [2026]
    assert all(body["coverage"].values())
    assert body["facts"]["status"] == "pending"  # never extracted on page load
    rows = body["compensation"]["rows"]
    assert rows[0]["role"] == "peo" and rows[0]["fiscal_year"] == 2026
    assert body["pay_ratio"]["ratio"] == "129.00000000" and body["pay_ratio"]["ceo_total"]
    assert len(body["pay_vs_performance"]["points"]) == 5

    llm = _Recorded()
    assert tier_c.extract_document_facts(session, document, llm=llm) is True
    assert tier_c.extract_document_facts(session, document, llm=llm) is False  # cached
    assert llm.calls == 1
    facts = client.get("/api/v1/companies/NVDA/governance?fiscal_year=2026").json()["facts"]
    assert facts["status"] == "extracted" and facts["model"] == "mock"
    by_name = {f["name"]: f for f in facts["fields"]}
    assert by_name["board_size"]["value"] == "10" and by_name["board_size"]["quote"]
    assert by_name["dual_class"]["value"] is None  # not stated
    assert facts["independence_ratio"] is None  # needs both counts

    history = client.get("/api/v1/companies/NVDA/governance/history").json()["points"]
    years = {p["fiscal_year"]: p for p in history}
    assert years[2026]["ceo_total_pay_source"] == "summary_compensation_table"
    assert years[2022]["ceo_total_pay_source"] == "pay_versus_performance"
    assert client.get("/api/v1/companies/NVDA/governance?fiscal_year=2019").status_code == 404


def test_empty_state_says_nothing_was_ingested(
    session: Session, client: TestClient, tmp_path: Path
) -> None:
    ingest_company(session, "JPM", sec=MockSecSource(), storage=FilesystemObjectStorage(tmp_path))
    body = client.get("/api/v1/companies/JPM/governance").json()
    assert body["filing"] is None and body["proxies_ingested"] == 0
    assert body["reason"] == "No DEF 14A proxy statement has been processed for this company yet."
    assert client.get("/api/v1/companies/JPM/governance/history").json()["points"] == []


def test_unreadable_proxy_and_no_evidence(session: Session, tmp_path: Path) -> None:
    storage = FilesystemObjectStorage(tmp_path)
    company = _company(session, "NVDA", storage)

    def broken(_key: str) -> bytes:
        raise OSError("storage offline")

    assert build_company_governance(session, company, read_raw=broken).proxies == 0
    filing = session.scalars(
        select(Filing).where(Filing.company_id == company.id, Filing.filing_type == "DEFA14A")
    ).one()
    supplemental = session.get(Document, filing.document_id)
    assert supplemental is not None
    # A proxy with no paragraph about the board makes no model call and says so.
    assert tier_c.extract_document_facts(session, supplemental, llm=_Recorded()) is False
    assert tier_c.cached_facts(supplemental, "mock") == {"no_evidence": True, "model": "mock"}
