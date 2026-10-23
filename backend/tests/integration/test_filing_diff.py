"""Filing diff, risk change status, new-risk alert, management language, earnings reaction
(spec §37.3-§37.5, Phase 6b DoD). Real Postgres; skips offline.

Seeds one company with four annual 10-Ks whose risk factors and MD&A change in known ways, then
checks the API, the report wiring, and the alert against that ground truth.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.alerts.dispatch import check_and_dispatch
from app.config import get_settings
from app.db import get_db
from app.filings.service import change_statuses, diff_filings
from app.ingestion.documents.chunker import PARSER_VERSION
from app.main import app
from app.models import (
    Alert,
    Company,
    Document,
    DocumentChunk,
    Filing,
    Notification,
    PriceHistory,
    User,
)
from app.research.report import _annotate_risk_changes
from app.schemas.research import Risk
from tests.fakes import FakeLLM

_P = "/api/v1"
_SUPPLY = "Our suppliers are concentrated in Asia. A disruption there would cut what we can ship."
_RIVALS = "Rivals are larger than we are. They spent $5 billion on research in fiscal 2024."
_DEBT = "We owe lenders under our notes. Servicing that debt limits what we can invest."
_EXPORT = "Export licences are now required for our fastest chips. Sales to China could stop."

_PREAMBLE = "Risk Factors\n\nThe risks below could harm us. Read them with the rest of this report."

# (period_end, risk factors [(caption, body)], MD&A text) — oldest first.
_YEARS: list[tuple[date, list[tuple[str, str]], str]] = [
    (
        date(2022, 12, 31),
        [("Competition could hurt us.", _RIVALS), ("Our debt could limit us.", _DEBT)],
        "Gross margin was stable. Demand may soften. " + "Revenue grew this year. " * 20,
    ),
    (
        date(2023, 12, 31),
        [("Competition could hurt us.", _RIVALS), ("Our debt could limit us.", _DEBT)],
        "Gross margin was stable. Supply chain costs rose. " + "Revenue grew this year. " * 20,
    ),
    (
        date(2024, 12, 31),
        [
            ("Competition could hurt us.", _RIVALS),
            ("We depend on suppliers.", _SUPPLY),
            ("Our debt could limit us.", _DEBT),
        ],
        "Gross margin fell. AI demand was strong. AI may grow. " + "Revenue grew this year. " * 20,
    ),
    (
        date(2025, 12, 31),
        [
            ("Competition could hurt us.", _RIVALS.replace("5", "7").replace("2024", "2025")),
            ("We depend on suppliers.", _SUPPLY + " Lead times have doubled since last year."),
            ("Export controls may restrict our sales.", _EXPORT),
        ],
        "AI demand was strong. AI could grow again. " + "Revenue grew this year. " * 20,
    ),
]


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


def _add_filing(
    session: Session,
    company: Company,
    *,
    filing_type: str,
    period_end: date,
    sections: list[tuple[str, str, str]],
    items: list[str] | None = None,
    created_at: datetime | None = None,
) -> Filing:
    """One filing; `sections` are (section_path key, section title, chunk text)."""
    accession = f"{company.cik}-{filing_type}-{period_end.isoformat()}"
    doc = Document(
        company_id=company.id, document_type="filing", source_tier=1, content_hash=accession
    )
    session.add(doc)
    session.flush()
    filing = Filing(
        document_id=doc.id,
        company_id=company.id,
        filing_type=filing_type,
        filing_date=period_end + timedelta(days=30),
        period_end=period_end,
        accession_number=accession,
        items=items,
    )
    if created_at is not None:
        filing.created_at = created_at
    session.add(filing)
    for index, (key, title, text) in enumerate(sections):
        session.add(
            DocumentChunk(
                document_id=doc.id,
                company_id=company.id,
                chunk_index=index,
                chunk_type="text",
                text=text,
                section=title,
                section_path=[key],
                paragraph_id=f"{doc.id}_{key.removeprefix('Item ')}_{index}",
                char_start=0,
                char_end=len(text),
                tier=1,
                filing_type=filing_type,
                parser_version=PARSER_VERSION,  # the diff reads current-parser chunks only
            )
        )
    session.flush()
    return filing


def _seed(session: Session, *, years: int = 4) -> tuple[Company, list[Filing]]:
    company = Company(ticker="DIF", cik="0000000042", name="Diff Corp")
    session.add(company)
    session.flush()
    filings = [
        _add_filing(
            session,
            company,
            filing_type="10-K",
            period_end=period_end,
            sections=[
                ("Item 1A", "Item 1A. Risk Factors", _PREAMBLE),
                *[("Item 1A", "Item 1A. Risk Factors", f"{cap}\n\n{body}") for cap, body in risks],
                ("Item 7", "Item 7. Management's Discussion and Analysis", mda),
            ],
            created_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i),
        )
        for i, (period_end, risks, mda) in enumerate(_YEARS[:years])
    ]
    return company, filings


def _by_heading(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {(item["new"] or item["old"])["heading"]: item for item in body["items"]}


# --- GET /filings/{id}/diff ---------------------------------------------------------------------


def test_diff_endpoint_classifies_and_cites_both_filings(
    client: TestClient, session: Session
) -> None:
    """§37.4 + CIT-001: each result carries its status and resolvable source IDs for the old and
    the new passage; `against` defaults to the prior filing of the same type."""
    _company, filings = _seed(session)
    latest, previous = filings[-1], filings[-2]

    resp = client.get(f"{_P}/filings/{latest.id}/diff", params={"kind": "risk_factor"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["against"]["filing_id"] == str(previous.id)
    assert body["similarity_method"] == "lexical"
    assert body["caption_detection"] == "heuristic"  # no raw document in object storage here
    assert body["counts"] == {"unchanged": 2, "reworded": 1, "new": 1, "removed": 1}

    items = _by_heading(body)
    assert items["Competition could hurt us."]["status"] == "unchanged"  # only digits moved
    assert items["Export controls may restrict our sales."]["status"] == "new"
    assert items["Our debt could limit us."]["status"] == "removed"
    reworded = items["We depend on suppliers."]
    assert reworded["status"] == "reworded"
    inserted = [op["text"] for op in reworded["word_diff"] if op["op"] == "insert"]
    assert inserted == ["Lead times have doubled since last year."]

    # Both passages are cited, and each ID resolves through the Phase 3a source endpoint.
    old_ids = reworded["old"]["source_ids"]
    new_ids = reworded["new"]["source_ids"]
    assert old_ids and new_ids and set(old_ids).isdisjoint(new_ids)
    for source_id in (*old_ids, *new_ids):
        source = client.get(f"{_P}/sources/{source_id}")
        assert source.status_code == 200, source.text

    explicit = client.get(f"{_P}/filings/{latest.id}/diff", params={"against": str(filings[0].id)})
    assert explicit.status_code == 200 and explicit.json()["against"]["filing_id"] == str(
        filings[0].id
    )


def test_diff_endpoint_rejects_incomparable_filings(client: TestClient, session: Session) -> None:
    """§37.4: only two filings of the same type from the same company can be compared."""
    company, filings = _seed(session)
    eight_k = _add_filing(
        session, company, filing_type="8-K", period_end=date(2025, 6, 30), sections=[]
    )
    assert client.get(f"{_P}/filings/{filings[0].id}/diff").status_code == 404  # nothing earlier
    mismatch = client.get(f"{_P}/filings/{filings[-1].id}/diff", params={"against": eight_k.id})
    assert mismatch.status_code == 422
    assert mismatch.headers["content-type"] == "application/problem+json"
    assert client.get(f"{_P}/filings/999999/diff").status_code == 404


# --- Risk.change_status (§10.10 v2) -------------------------------------------------------------


def test_report_risks_get_change_status_from_the_diff(session: Session) -> None:
    """§10.10 v2 + NFR-009: `change_status` comes from the deterministic diff of the cited
    passage; a source outside the latest filing gets no status rather than a guess."""
    _company, filings = _seed(session)
    latest, previous, oldest = filings[-1], filings[-2], filings[0]
    doc, prev_doc = latest.document_id, previous.document_id
    risks = [
        Risk(category="competitive", description="Rivals.", source_ids=[f"{doc}_1A_1"]),
        Risk(category="supply_chain", description="Suppliers.", source_ids=[f"{doc}_1A_2"]),
        Risk(category="regulatory", description="Exports.", source_ids=[f"{doc}_1A_3"]),
        Risk(category="business", description="Debt.", source_ids=[f"{prev_doc}_1A_3"]),
        Risk(category="business", description="Old.", source_ids=[f"{oldest.document_id}_1A_1"]),
        Risk(category="business", description="Unknown.", source_ids=["no-such-source"]),
    ]

    _annotate_risk_changes(session, risks, llm=FakeLLM(), settings=get_settings(), user_id=None)

    assert [r.change_status for r in risks] == [
        "unchanged",
        "reworded",
        "new",
        "removed",
        None,
        None,
    ]
    assert change_statuses(session, []) == {}


# --- "new risk factor detected" alert (§37.4, FR-007) -------------------------------------------


def test_new_risk_factor_alert_fires_once_for_a_new_filing(session: Session) -> None:
    """FR-007 / §37.4: ingesting a filing that adds a risk factor notifies the user once; a filing
    that adds none sends nothing and is not re-diffed on the next run."""
    company, filings = _seed(session, years=2)  # year 2 adds no risk factor
    user = User(email="risk-alerts@example.com", password_hash="x")  # noqa: S106
    session.add(user)
    session.flush()
    alert = Alert(user_id=user.id, company_id=company.id, event_type="new_risk_factor")
    session.add(alert)
    session.flush()

    # The seeded filings are as old as the alert, so nothing replays (FR-AL-005).
    assert check_and_dispatch(session) == 0
    assert alert.watermark_at > filings[-1].created_at  # watermark moved past them

    # Simulated new-filing scenario: next year's 10-K arrives with a supplier risk factor.
    period_end, risk_factors, mda = _YEARS[2]
    _add_filing(
        session,
        company,
        filing_type="10-K",
        period_end=period_end,
        sections=[
            ("Item 1A", "Item 1A. Risk Factors", _PREAMBLE),
            *[
                ("Item 1A", "Item 1A. Risk Factors", f"{cap}\n\n{body}")
                for cap, body in risk_factors
            ],
            ("Item 7", "Item 7. Management's Discussion and Analysis", mda),
        ],
        created_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    assert check_and_dispatch(session, now=datetime.now(UTC) + timedelta(minutes=5)) == 1
    note = session.scalars(select(Notification).where(Notification.user_id == user.id)).one()
    assert note.title == "New risk factor in DIF 10-K"
    assert "We depend on suppliers." in (note.body or "")

    assert check_and_dispatch(session, now=datetime.now(UTC) + timedelta(minutes=10)) == 0


# --- management language (§37.5) ----------------------------------------------------------------


def test_management_language_series_over_four_periods(client: TestClient, session: Session) -> None:
    """§37.5 + CIT-001: per-period intensity per 1,000 words, appearance flags, a lexicon hedging
    index, and for every counted mention the statement and a resolvable source ID."""
    _seed(session)
    resp = client.get(f"{_P}/companies/DIF/management-language")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["taxonomy_version"] == "topic_taxonomy_v1"
    assert "not an AI judgment" in body["method"]
    assert [p["period_end"] for p in body["periods"]] == [
        "2022-12-31",
        "2023-12-31",
        "2024-12-31",
        "2025-12-31",
    ]
    series = {s["topic"]: s["points"] for s in body["topics"]}
    assert [p["count"] for p in series["ai_demand"]] == [0, 0, 2, 2]
    assert [p["flag"] for p in series["ai_demand"]] == [None, None, "first_appearance", None]
    assert [p["flag"] for p in series["margins"]] == [None, None, None, "disappeared"]
    assert [p["flag"] for p in series["supply_chain"]] == [
        None,
        "first_appearance",
        "disappeared",
        None,
    ]

    words = body["periods"][2]["word_count"]
    point = series["ai_demand"][2]
    assert point["per_1k_words"] == round(2 * 1000 / words, 3)
    assert sum(s["mentions"] for s in point["statements"]) == point["count"]
    for statement in point["statements"]:
        assert "AI" in statement["text"]
        assert client.get(f"{_P}/sources/{statement['source_id']}").status_code == 200

    assert [p["count"] for p in body["hedging"]["points"]] == [1, 0, 1, 1]
    assert client.get(f"{_P}/companies/NOPE/management-language").status_code == 404


# --- earnings-day price reaction (§37.3) --------------------------------------------------------


def test_earnings_reaction_is_deterministic_decimal(client: TestClient, session: Session) -> None:
    """§37.3 + NFR-009: the move around an Item 2.02 8-K is exact Decimal arithmetic on adjusted
    closes; with no prices it is N/A with a reason, never 0."""
    company, _ = _seed(session, years=1)
    for day, adj_close in ((27, "100"), (28, "100"), (30, "108.5")):  # the 29th has no session
        session.add(
            PriceHistory(
                company_id=company.id,
                date=date(2025, 8, day),
                close=Decimal(adj_close),
                adj_close=Decimal(adj_close),
            )
        )
    # filing_date = period_end + 30 days -> 2025-08-29 and 2020-03-31.
    for period_end, items in (
        (date(2025, 7, 30), ["2.02", "9.01"]),
        (date(2020, 3, 1), ["2.02"]),
        (date(2025, 7, 29), ["5.02"]),  # not an earnings release
    ):
        _add_filing(
            session, company, filing_type="8-K", period_end=period_end, sections=[], items=items
        )

    resp = client.get(f"{_P}/companies/DIF/earnings")
    assert resp.status_code == 200, resp.text
    recent, old = resp.json()["events"]

    assert (recent["pre_date"], recent["post_date"]) == ("2025-08-28", "2025-08-30")
    assert Decimal(recent["move"]) == Decimal("0.085")
    assert Decimal(recent["pre_close"]) == Decimal("100")
    assert old["move"] is None and old["reason"] == "NO_PRICE_DATA"


def test_diff_service_reports_caption_detection(session: Session) -> None:
    """§37.4: without raw documents the diff degrades to guessed captions and says so."""
    _company, filings = _seed(session)
    assert diff_filings(session, filings[-1], filings[-2]).caption_detection == "heuristic"
