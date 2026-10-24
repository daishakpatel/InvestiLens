"""Footnote facts, notes, summaries and the note-scoped diff (Phase 7f). Real Postgres, mock SEC.

Requirement IDs: FR-FN-001/003/004/005/006/007/009/010/011, AGT-FN-002.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
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
from app.finance.builder import build_company_metrics
from app.finance.footnote_builder import (
    FILING_UNAVAILABLE,
    NOT_TAGGED,
    FootnoteCounts,
    build_company_footnotes,
)
from app.finance.ratio_builder import build_company_ratios
from app.footnotes import summary
from app.ingestion.documents.pipeline import parse_and_chunk, parse_company_documents
from app.ingestion.sec import ingest_company
from app.main import app
from app.models import Company, Document, Filing, FinancialMetric, LlmCall, MetricGap
from app.providers.base import LLMClient
from app.providers.mocks._fixtures import fixture_gzip_bytes
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
def client(session: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(session, "commit", session.flush)
    app.dependency_overrides[get_db] = lambda: session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _company(
    session: Session, ticker: str, storage: FilesystemObjectStorage, *, parse: bool = False
) -> tuple[Company, FootnoteCounts]:
    """The production order: metrics, ratios, then footnotes (which add to total debt)."""
    ingest_company(session, ticker, sec=MockSecSource(), storage=storage)
    company = session.scalars(select(Company).where(Company.ticker == ticker)).one()
    if parse:
        parse_company_documents(session, company.id, storage=storage, filing_types=("10-K",))
    build_company_metrics(session, company)
    build_company_ratios(session, company)
    return company, build_company_footnotes(session, company, read_raw=storage.get)


def _rows(session: Session, company: Company, period: str) -> dict[str, FinancialMetric]:
    rows = session.scalars(
        select(FinancialMetric).where(
            FinancialMetric.company_id == company.id,
            FinancialMetric.period == period,
            FinancialMetric.is_latest.is_(True),
        )
    )
    return {row.metric_name: row for row in rows}


def _gaps(session: Session, company: Company) -> dict[str, str]:
    rows = session.scalars(select(MetricGap).where(MetricGap.company_id == company.id))
    return {g.metric: g.reason for g in rows if g.period_label.startswith("FY")}


_LADDER = ("y1", "y2", "y3", "y4", "y5", "after")


def test_aapl_ladder_from_companyfacts_matches_the_filing(session: Session, tmp_path: Path) -> None:
    """Hand check: Apple 2025 Form 10-K, Note 9 Debt (pages 43-44), "The future principal
    payments for the Company's Notes as of September 27, 2025": 2026 $12,393M; 2027 $10,078M;
    2028 $9,300M; 2029 $5,235M; 2030 $4,972M; thereafter $49,303M; total $91,281M."""
    company, _ = _company(session, "AAPL", FilesystemObjectStorage(tmp_path))
    rows = _rows(session, company, "FY2025")
    ladder = [rows[f"debt_maturity_{b}"].metric_value for b in _LADDER]
    millions = [12_393, 10_078, 9_300, 5_235, 4_972, 49_303]
    assert ladder == [Decimal(m) * 1_000_000 for m in millions]
    y1 = rows["debt_maturity_y1"]
    assert y1.source_id == "xbrl:AAPL:debt_maturity_y1:FY2025" and not y1.is_derived
    assert y1.source_tag == "us-gaap:LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths"
    share = rows["debt_due_within_2y_share"]
    assert share.metric_value == pytest.approx(
        Decimal(22_471) / Decimal(91_281), rel=Decimal("1e-6")
    )


def test_nvda_ladder_from_inline_xbrl_matches_the_filing(session: Session, tmp_path: Path) -> None:
    """Hand check: NVIDIA FY2026 10-K, Note 11 Debt, notes table ("Expected Remaining Term
    (years)", "Jan 25, 2026"): $1,000M due within a year (2026 Notes, 0.6y), $1,250M in year 3
    (2028, 2.4y), $1,500M in year 5 (2030, 4.2y), $4,750M after (2031/2040/2050/2060 Notes)."""
    company, _ = _company(session, "NVDA", FilesystemObjectStorage(tmp_path))
    rows = _rows(session, company, "FY2026")
    ladder = [rows[f"debt_maturity_{b}"].metric_value for b in _LADDER]
    assert ladder == [Decimal(m) * 1_000_000 for m in (1_000, 0, 1_250, 0, 1_500, 4_750)]
    after = rows["debt_maturity_after"]
    assert after.is_derived and after.source_id == "derived:NVDA:debt_maturity_after:FY2026"
    names = [i["name"] for i in (after.quality_flags or {})["inputs"]]
    assert names == [
        "nvda:A2031NotesMember (5.4 years remaining)",
        "nvda:A2040NotesMember (14.2 years remaining)",
        "nvda:A2050NotesMember (24.2 years remaining)",
        "nvda:A2060NotesMember (34.2 years remaining)",
    ]
    # The lease term companyfacts drops, read from the same 10-K.
    term = rows["operating_lease_wa_term_years"]
    assert term.metric_value == Decimal("8.8") and term.unit == "years"
    assert (term.quality_flags or {})["source"] == "inline_xbrl"
    # The drawer lists every note behind a window (CIT-003).
    detail = resolve_source(session, "derived:NVDA:debt_maturity_y1:FY2026")
    assert detail is not None and detail.lineage == [
        {"name": "nvda:A2026NotesMember (0.6 years remaining)", "value": "1000000000"}
    ]


def test_missing_concepts_are_gaps_never_zeros(session: Session, tmp_path: Path) -> None:
    company, counts = _company(session, "AAPL", FilesystemObjectStorage(tmp_path))
    gaps = _gaps(session, company)
    assert gaps["revolver_capacity"] == NOT_TAGGED
    assert gaps["operating_lease_wa_term_years"] == NOT_TAGGED  # not in the 10-K either
    assert counts.gaps == len(gaps)
    rows = _rows(session, company, "FY2025")
    assert not set(gaps) & set(rows)  # a gap is a missing row, not a zero row
    # Re-running replaces the builder's own gaps and leaves the quarterly ones alone.
    quarterly = session.scalars(
        select(MetricGap).where(
            MetricGap.company_id == company.id, MetricGap.period_label.like("Q%")
        )
    ).all()
    build_company_footnotes(session, company, read_raw=FilesystemObjectStorage(tmp_path).get)
    assert _gaps(session, company) == gaps
    assert len(
        session.scalars(
            select(MetricGap).where(
                MetricGap.company_id == company.id, MetricGap.period_label.like("Q%")
            )
        ).all()
    ) == len(quarterly)


def test_unreadable_10k_degrades_to_gaps(session: Session, tmp_path: Path) -> None:
    storage = FilesystemObjectStorage(tmp_path)
    company, _ = _company(session, "NVDA", storage)

    def broken(_key: str) -> bytes:
        raise OSError("storage offline")

    build_company_footnotes(session, company, read_raw=broken)
    gaps = _gaps(session, company)
    assert gaps["debt_maturity_y1"] == FILING_UNAVAILABLE
    assert gaps["debt_due_within_2y_share"] == "MISSING_INPUT"
    assert "debt_maturity_y1" not in _rows(session, company, "FY2026")

    # A 10-K whose raw document was never stored degrades the same way.
    ten_k = session.scalars(
        select(Filing).where(Filing.company_id == company.id, Filing.filing_type == "10-K")
    ).one()
    ten_k.raw_document_location = None
    build_company_footnotes(session, company, read_raw=storage.get)
    assert _gaps(session, company)["operating_lease_wa_term_years"] == FILING_UNAVAILABLE


def test_lease_adjusted_debt_inputs_resolve(session: Session, tmp_path: Path) -> None:
    company, _ = _company(session, "NVDA", FilesystemObjectStorage(tmp_path))
    row = _rows(session, company, "FY2026")["lease_adjusted_debt"]
    flags = row.quality_flags or {}
    assert flags["derived"] == "total debt + operating lease liabilities"
    inputs = {i["name"]: i for i in flags["inputs"]}
    assert set(inputs) == {"total_debt", "operating_lease_liability"}
    assert row.metric_value == sum(Decimal(i["value"]) for i in inputs.values())
    for item in inputs.values():
        assert resolve_source(session, item["source_id"]) is not None
    assert resolve_source(session, "derived:NVDA:lease_adjusted_debt:FY2026") is not None


def test_footnote_facts_endpoint(session: Session, client: TestClient, tmp_path: Path) -> None:
    _company(session, "NVDA", FilesystemObjectStorage(tmp_path))
    body = client.get("/api/v1/companies/NVDA/footnote-facts").json()
    assert body["fiscal_year"] == 2026
    groups = {c["category"]: c for c in body["categories"]}
    assert list(groups) == [
        "debt",
        "leases",
        "income_taxes",
        "commitments_contingencies",
        "stock_comp",
    ]
    debt = {f["metric"]: f for f in groups["debt"]["facts"]}
    assert debt["total_debt"]["is_derived"] and "debt_maturity_y3" in debt
    leases = {f["metric"]: f for f in groups["leases"]["facts"]}
    assert leases["lease_adjusted_debt"]["label"] == "Lease-adjusted debt"
    assert leases["operating_lease_wa_term_years"]["from_inline_xbrl"]
    assert {g["metric"] for g in groups["debt"]["gaps"]} == {
        "debt_weighted_avg_rate",
        "revolver_capacity",
    }
    stock = {f["metric"] for f in groups["stock_comp"]["facts"]}
    assert stock == {"stock_based_compensation", "unrecognized_sbc_cost"}


def test_footnote_facts_before_any_build(
    session: Session, client: TestClient, tmp_path: Path
) -> None:
    ingest_company(session, "JPM", sec=MockSecSource(), storage=FilesystemObjectStorage(tmp_path))
    body = client.get("/api/v1/companies/JPM/footnote-facts").json()
    assert body == {"company_ticker": "JPM", "fiscal_year": None, "categories": []}


# --- notes, summaries, scoped diff ------------------------------------------------------
class _Recorded(LLMClient):
    """A model that answers every note with one bullet quoting the note's first paragraph."""

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, messages: Any, *, model: str, max_tokens: int) -> str:
        raise NotImplementedError

    async def complete_json(
        self, messages: Any, *, model: str, schema: dict[str, Any], max_tokens: int
    ) -> dict[str, Any]:
        self.calls += 1
        user = messages[1].content
        pid = user.split("[paragraph_id=", 1)[1].split("]", 1)[0]
        body = user.split(f"[paragraph_id={pid}]\n", 1)[1].split("\n", 1)[1]
        words = " ".join(body.split()[3:13])  # past the "Note N - Title" heading
        if "Segment" in user.split("NOTE TITLE:", 1)[1][:200]:
            return {"bullets": [], "abstain": True}
        bullet = {"text": "The note describes this.", "quote": words, "paragraph_id": pid}
        return {"bullets": [bullet], "abstain": False}


def test_parse_stores_notes_and_summaries_are_cached(
    session: Session, client: TestClient, tmp_path: Path
) -> None:
    company, _ = _company(session, "NVDA", FilesystemObjectStorage(tmp_path), parse=True)
    filing = session.scalars(
        select(Filing).where(Filing.company_id == company.id, Filing.filing_type == "10-K")
    ).one()
    document = session.get(Document, filing.document_id)
    assert document is not None
    stored = (document.doc_metadata or {})["notes"]
    assert stored["taxonomy"] == "note_taxonomy_v1" and len(stored["items"]) == 17

    body = client.get("/api/v1/companies/NVDA/notes").json()
    assert all(n["summary"]["status"] == "pending" for n in body["notes"] if n["summary"])

    # NVIDIA has no revenue-recognition note: commitments and segments are summarised.
    llm = _Recorded()
    assert summary.summarize_document_notes(session, document, llm=llm) == 2
    assert summary.summarize_document_notes(session, document, llm=llm) == 0  # cached
    assert llm.calls == 2
    calls = session.scalars(select(LlmCall).where(LlmCall.purpose == "note_summary")).all()
    assert len(calls) == 2 and calls[0].prompt_version == "note_summary_v1"

    body = client.get(f"/api/v1/companies/NVDA/notes?filing_id={filing.id}").json()
    assert not body["low_confidence"] and body["filing"]["filing_id"] == str(filing.id)
    by_category = {n["category"]: n for n in body["notes"]}
    assert by_category["commitments_contingencies"]["summary"]["status"] == "summarised"
    bullet = by_category["commitments_contingencies"]["summary"]["bullets"][0]
    assert bullet["paragraph_id"] in by_category["commitments_contingencies"]["paragraph_ids"]
    assert by_category["segments"]["summary"]["status"] == "abstained"  # "Not summarised"
    assert by_category["debt"]["summary"] is None  # numbers come from XBRL, not a summary

    # A re-parse rewrites the notes and drops the summaries that cited the old chunks.
    raw = fixture_gzip_bytes("nvda", "10k.htm.gz")
    parse_and_chunk(session, filing, storage=FilesystemObjectStorage(tmp_path), html_bytes=raw)
    assert summary.CACHE_KEY not in (document.doc_metadata or {})


def test_notes_endpoint_errors(session: Session, client: TestClient, tmp_path: Path) -> None:
    company, _ = _company(session, "NVDA", FilesystemObjectStorage(tmp_path))
    assert client.get("/api/v1/companies/NVDA/notes").status_code == 404  # nothing parsed yet
    eight_k = session.scalars(
        select(Filing).where(Filing.company_id == company.id, Filing.filing_type == "8-K")
    ).first()
    assert eight_k is not None
    assert client.get(f"/api/v1/companies/NVDA/notes?filing_id={eight_k.id}").status_code == 422
    ten_k = session.scalars(
        select(Filing).where(Filing.company_id == company.id, Filing.filing_type == "10-K")
    ).one()
    unsegmented = client.get(f"/api/v1/companies/NVDA/notes?filing_id={ten_k.id}").json()
    assert unsegmented["low_confidence"] and unsegmented["notes"] == []


def _latest_10k(session: Session, company: Company) -> Filing:
    return session.scalars(
        select(Filing).where(
            Filing.company_id == company.id,
            Filing.filing_type == "10-K",
            Filing.accession_number != "older-10k",
        )
    ).one()


def _older_10k(session: Session, company: Company, storage: FilesystemObjectStorage) -> Filing:
    """Last year's 10-K: the same filing with the debt note's covenant sentence reworded."""
    html = fixture_gzip_bytes("nvda", "10k.htm.gz").decode("utf-8", "ignore")
    edited = html.replace("we complied with the required covenants", "we met every covenant")
    assert edited != html
    key = storage.put("test/nvda-older-10k.htm", edited.encode())
    document = Document(
        company_id=company.id, document_type="filing", source_tier=1, content_hash="older-10k"
    )
    session.add(document)
    session.flush()
    latest = session.scalars(
        select(Filing).where(Filing.company_id == company.id, Filing.filing_type == "10-K")
    ).one()
    assert latest.filing_date is not None
    older = Filing(
        document_id=document.id,
        company_id=company.id,
        filing_type="10-K",
        filing_date=latest.filing_date - timedelta(days=365),
        period_end=date(2025, 1, 26),
        accession_number="older-10k",
        raw_document_location=key,
    )
    session.add(older)
    session.flush()
    parse_and_chunk(session, older, storage=storage)
    return older


def test_note_scoped_diff_reuses_the_filing_diff(
    session: Session, client: TestClient, tmp_path: Path
) -> None:
    storage = FilesystemObjectStorage(tmp_path)
    company, _ = _company(session, "NVDA", storage, parse=True)
    older = _older_10k(session, company, storage)
    latest = _latest_10k(session, company)

    body = client.get(f"/api/v1/filings/{latest.id}/notes/debt/diff").json()
    assert body["against"]["filing_id"] == str(older.id)
    changed = [i for i in body["items"] if i["status"] != "unchanged"]
    assert [i["status"] for i in changed] == ["reworded"]
    words = {op["text"] for op in changed[0]["word_diff"] if op["op"] != "equal"}
    assert "complied with the required covenants," in words or any("complied" in w for w in words)
    # Only the debt note's passages are compared.
    debt_ids = set()
    for filing in (latest, older):
        document = session.get(Document, filing.document_id)
        assert document is not None
        for note in (document.doc_metadata or {})["notes"]["items"]:
            if note["category"] == "debt":
                debt_ids |= set(note["paragraph_ids"])
    for item in body["items"]:
        for side in ("old", "new"):
            if item[side]:
                assert set(item[side]["source_ids"]) <= debt_ids

    # Without a scope the whole filing is compared, as before.
    whole = client.get(f"/api/v1/filings/{latest.id}/diff").json()
    assert sum(whole["counts"].values()) > sum(body["counts"].values())

    assert client.get(f"/api/v1/filings/{latest.id}/notes/pensions/diff").status_code == 404


def test_note_diff_needs_the_note_in_both_filings(
    session: Session, client: TestClient, tmp_path: Path
) -> None:
    storage = FilesystemObjectStorage(tmp_path)
    company, _ = _company(session, "NVDA", storage, parse=True)
    older = _older_10k(session, company, storage)
    document = session.get(Document, older.document_id)
    assert document is not None
    metadata = dict(document.doc_metadata or {})
    metadata["notes"] = {**metadata["notes"], "items": []}
    document.doc_metadata = metadata
    session.flush()
    latest = _latest_10k(session, company)
    response = client.get(f"/api/v1/filings/{latest.id}/notes/debt/diff?against={older.id}")
    assert response.status_code == 422
