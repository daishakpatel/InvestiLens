"""Red-flag detection, persistence, API, citations and alerts (Phase 7e). Real Postgres, mock SEC.

Requirement IDs: FR-RF-006 … FR-RF-013, DR-RF-001 … DR-RF-003.
"""

from __future__ import annotations

import gzip
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.alerts.dispatch import check_and_dispatch
from app.citation.resolver import resolve_source
from app.db import get_db
from app.ingestion.documents.pipeline import parse_and_chunk, parse_company_documents
from app.ingestion.sec import ingest_company
from app.main import app
from app.models import (
    Alert,
    Company,
    Document,
    Filing,
    Notification,
    RedFlag,
    User,
    Watchlist,
    WatchlistItem,
)
from app.providers.sec.mock import MockSecSource
from app.redflags import taxonomy
from app.redflags.detect import scan_company
from app.utils.storage import FilesystemObjectStorage
from tests.fakes import auth_headers

_P = "/api/v1"
_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "redflags"


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


def _nvda(session: Session, tmp_path: Path) -> Company:
    storage = FilesystemObjectStorage(tmp_path)
    ingest_company(session, "NVDA", sec=MockSecSource(), storage=storage)
    company = session.scalars(select(Company).where(Company.ticker == "NVDA")).one()
    parse_company_documents(session, company.id, storage=storage)
    return company


def _filing(
    session: Session,
    company: Company,
    *,
    fixture: str | None,
    items: list[str],
    accession: str,
    filed: date,
    form: str = "8-K",
) -> Filing:
    """A filing parsed from a fixture file, as ingestion + parsing would store it."""
    document = Document(
        company_id=company.id, document_type="filing", source_tier=1, content_hash=accession
    )
    session.add(document)
    session.flush()
    filing = Filing(
        document_id=document.id,
        company_id=company.id,
        filing_type=form,
        filing_date=filed,
        accession_number=accession,
        items=items,
        primary_document_url=f"https://www.sec.gov/Archives/{accession}.htm",
    )
    session.add(filing)
    session.flush()
    if fixture is not None:
        html = gzip.decompress((_FIXTURES / fixture).read_bytes())
        parse_and_chunk(
            session, filing, storage=FilesystemObjectStorage(Path("/nonexistent")), html_bytes=html
        )
    return filing


def _flags(session: Session, company: Company, **where: object) -> list[RedFlag]:
    query = select(RedFlag).where(RedFlag.company_id == company.id)
    for column, value in where.items():
        query = query.where(getattr(RedFlag, column) == value)
    return list(session.scalars(query))


def test_nt_10k_fixture_yields_late_filing_notice(session: Session, tmp_path: Path) -> None:
    """FR-RF-001: the (synthetic, labelled) NT 10-K and NT 10-Q fixtures flag a late filing."""
    company = _nvda(session, tmp_path)
    scan_company(session, company)
    late = _flags(session, company, rule_key="late_filing_notice")
    forms = {session.get(Filing, f.filing_id).filing_type for f in late}  # type: ignore[union-attr]
    assert forms == {"NT 10-K", "NT 10-Q"}
    assert all(f.severity == "warning" and "Form 12b-25" in f.snippet for f in late)


def test_item_402_fixture_flags_non_reliance_with_filing_and_date(
    session: Session, tmp_path: Path
) -> None:
    """FR-RF-001/006: the 4.02 8-K yields `non_reliance` on that filing, dated by the filing."""
    company = _nvda(session, tmp_path)
    filing = _filing(
        session,
        company,
        fixture="synthetic_8k_402.htm.gz",
        items=["4.02", "9.01"],
        accession="0000000000-26-904020",
        filed=date(2026, 3, 3),
    )
    scan_company(session, company)
    [flag] = _flags(session, company, rule_key="non_reliance")
    assert flag.filing_id == filing.id and flag.document_id == filing.document_id
    assert flag.event_date == date(2026, 3, 3) and flag.severity == "critical"
    assert flag.paragraph_id is not None and "4.02" in flag.paragraph_id
    assert flag.snippet.startswith("On March 2, 2026, the Audit Committee")


def test_item_507_vote_8k_is_not_an_executive_departure(session: Session, tmp_path: Path) -> None:
    """FR-RF-004: the real NVIDIA 5.07 (shareholder vote) 8-K yields no departure flag: the old
    collapsed "5" code would have made it look like a 5.02."""
    company = _nvda(session, tmp_path)
    vote = _filing(
        session,
        company,
        fixture="nvda_8k_507.htm.gz",
        items=["5.07"],
        accession="0001045810-26-000056",
        filed=date(2026, 6, 30),
    )
    scan_company(session, company)
    assert not [f for f in _flags(session, company) if f.filing_id == vote.id]
    # The real 5.02 8-K in the mock manifest (March 2026) adopts a compensation plan: Item 5.02
    # without a departure, which must not fire either.
    assert not _flags(session, company, rule_key="exec_departure")
    assert not _flags(session, company, rule_key="exec_change_unspecified")


def test_item_205_real_8k_flags_restructuring(session: Session, tmp_path: Path) -> None:
    company = _nvda(session, tmp_path)
    filing = _filing(
        session,
        company,
        fixture="intc_8k_205.htm.gz",
        items=["2.02", "2.05", "9.01"],
        accession="0000050863-24-000147",
        filed=date(2024, 10, 31),
    )
    scan_company(session, company)
    [flag] = _flags(session, company, rule_key="restructuring")
    assert flag.filing_id == filing.id and flag.severity == "info"
    assert "Item 2.05" not in flag.snippet[:20]  # the quote is the item's text, not its title


def test_rescans_are_idempotent_and_a_new_version_adds_rows(
    session: Session, tmp_path: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DR-RF-001/002: a second scan stores nothing new; a new taxonomy version adds rows (keeping
    the first detection time), and the API serves only the newest version."""
    company = _nvda(session, tmp_path)
    first = scan_company(session, company)
    assert first.new_flags > 0
    count = len(_flags(session, company))
    assert scan_company(session, company).new_flags == 0
    assert len(_flags(session, company)) == count

    v1_seen = {(f.rule_key, f.filing_id): f.detected_at for f in _flags(session, company)}
    monkeypatch.setattr(taxonomy, "TAXONOMY_VERSION", "red_flag_taxonomy_v2")
    assert scan_company(session, company).new_flags == count
    v2 = _flags(session, company, taxonomy_version="red_flag_taxonomy_v2")
    assert len(v2) == count and len(_flags(session, company)) == 2 * count
    assert all(f.detected_at == v1_seen[(f.rule_key, f.filing_id)] for f in v2)

    body = client.get(f"{_P}/companies/NVDA/red-flags?limit=200").json()
    assert body["taxonomy_version"] == "red_flag_taxonomy_v2"
    assert len(body["items"]) == count  # v1 rows kept for audit, not served


def test_redflag_source_resolves_to_snippet_and_filing(
    session: Session, tmp_path: Path, client: TestClient
) -> None:
    """FR-RF-008: `redflag:` IDs resolve with the quoted text and a link to the filing; existing
    prefixes are unaffected."""
    company = _nvda(session, tmp_path)
    filing = _filing(
        session,
        company,
        fixture="synthetic_8k_402.htm.gz",
        items=["4.02"],
        accession="0000000000-26-904021",
        filed=date(2026, 3, 3),
    )
    scan_company(session, company)
    sid = f"redflag:NVDA:non_reliance:{filing.accession_number}"
    detail = resolve_source(session, sid)
    assert detail is not None and detail.source.source_type == "text_chunk"
    assert detail.text is not None and detail.text.startswith("On March 2, 2026")
    assert detail.deep_link == filing.primary_document_url
    assert resolve_source(session, "redflag:NVDA:non_reliance:0000000000-00-000000") is None
    assert resolve_source(session, "redflag:NVDA:not_a_rule:" + filing.accession_number) is None
    via_api = client.get(f"{_P}/sources/{sid}")
    assert via_api.status_code == 200 and via_api.json()["deep_link"] == filing.primary_document_url


def test_company_endpoint_items_filters_and_empty_state(
    session: Session, tmp_path: Path, client: TestClient
) -> None:
    """FR-RF-009/010: newest first with label, severity, date, snippet, filing and source ID; an
    empty result says when the company was last scanned."""
    company = _nvda(session, tmp_path)
    scan_company(session, company)
    body = client.get(f"{_P}/companies/NVDA/red-flags").json()
    items = body["items"]
    assert items and body["last_scanned_at"]
    dates = [i["event_date"] for i in items]
    assert dates == sorted(dates, reverse=True)
    first = items[0]
    assert {
        "label",
        "severity",
        "event_date",
        "snippet",
        "filing",
        "source_id",
        "explanation",
    } <= set(first)
    assert first["source_id"].startswith("redflag:NVDA:")
    warning = client.get(f"{_P}/companies/NVDA/red-flags?severity=warning").json()["items"]
    assert warning and all(i["severity"] in {"warning", "critical"} for i in warning)
    since = client.get(f"{_P}/companies/NVDA/red-flags?since=2026-06-01").json()["items"]
    assert all(i["event_date"] >= "2026-06-01" for i in since)

    quiet = Company(ticker="QUIET", cik="0000000099", name="Quiet Co")
    session.add(quiet)
    session.flush()
    before = client.get(f"{_P}/companies/QUIET/red-flags").json()
    assert before == {
        "items": [],
        "last_scanned_at": None,
        "taxonomy_version": taxonomy.TAXONOMY_VERSION,
    }
    scan_company(session, quiet)
    after = client.get(f"{_P}/companies/QUIET/red-flags").json()
    assert after["items"] == [] and after["last_scanned_at"] is not None
    assert client.get(f"{_P}/companies/NVDA/red-flags?severity=bad").status_code == 422


def test_watchlist_feed_is_scoped_to_the_caller(
    session: Session, tmp_path: Path, client: TestClient
) -> None:
    """FR-RF-009: `GET /red-flags?watchlist=true` covers the caller's watchlist only."""
    company = _nvda(session, tmp_path)
    scan_company(session, company)
    watcher = User(email="watch@example.com", password_hash="x")  # noqa: S106
    other = User(email="none@example.com", password_hash="x")  # noqa: S106
    session.add_all([watcher, other])
    session.flush()
    watchlist = Watchlist(user_id=watcher.id, name="NVDA")
    session.add(watchlist)
    session.flush()
    session.add(WatchlistItem(watchlist_id=watchlist.id, company_id=company.id))
    session.flush()

    mine = client.get(f"{_P}/red-flags?watchlist=true", headers=auth_headers(watcher.id)).json()
    assert mine["items"] and {i["ticker"] for i in mine["items"]} == {"NVDA"}
    empty = client.get(f"{_P}/red-flags?watchlist=true", headers=auth_headers(other.id)).json()
    assert empty == {
        "items": [],
        "last_scanned_at": None,
        "taxonomy_version": taxonomy.TAXONOMY_VERSION,
    }
    assert client.get(f"{_P}/red-flags?watchlist=true").status_code == 401
    only_feed = client.get(f"{_P}/red-flags?watchlist=false", headers=auth_headers(other.id))
    assert only_feed.status_code == 422


def _alert(session: Session, user: User, company: Company, **params: object) -> Alert:
    alert = Alert(user_id=user.id, company_id=company.id, event_type="red_flag", params=params)
    session.add(alert)
    session.flush()
    return alert


def _notes(session: Session, alert: Alert) -> list[Notification]:
    return list(session.scalars(select(Notification).where(Notification.alert_id == alert.id)))


def test_red_flag_alert_fires_once_and_respects_min_severity(
    session: Session, tmp_path: Path
) -> None:
    """FR-RF-011: a simulated new 4.02 filing alerts once with the neutral template; a
    `critical` floor skips a warning; history found by a backfill does not alert (DR-RF-003)."""
    company = _nvda(session, tmp_path)
    user = User(email="flags@example.com", password_hash="x")  # noqa: S106
    session.add(user)
    session.flush()
    warn = _alert(session, user, company)  # default min_severity: warning
    critical = _alert(session, user, company, min_severity="critical")

    today = datetime.now(UTC).date()
    new_402 = _filing(
        session,
        company,
        fixture=None,
        items=["4.02"],
        accession="0000000000-26-904022",
        filed=today,
    )
    _filing(
        session,
        company,
        fixture=None,
        items=["4.01"],
        accession="0000000000-26-904023",
        filed=today,
    )
    scan_company(session, company)  # also finds the fixtures' older NT forms and 8-Ks

    later = datetime.now(UTC) + timedelta(minutes=2)
    assert check_and_dispatch(session, now=later) == 3  # 4.02 + 4.01 to `warn`, 4.02 to `critical`
    by_key = {n.event_key: n for n in _notes(session, warn)}
    sid = f"redflag:NVDA:non_reliance:{new_402.accession_number}"
    assert set(by_key) == {sid, "redflag:NVDA:auditor_change:0000000000-26-904023"}
    label = "Non-reliance on previously issued financial statements"
    assert by_key[sid].body == f"Reported: {label} (filed {today.isoformat()})."
    assert [n.event_key for n in _notes(session, critical)] == [sid]
    # Old filings (the NT 10-K of March) were detected now but are history, not news.
    assert not any("late_filing_notice" in (n.event_key or "") for n in _notes(session, warn))
    assert check_and_dispatch(session, now=later + timedelta(minutes=5)) == 0  # exactly once
    assert session.scalar(select(func.count()).select_from(Notification)) == 3


def test_beneish_and_restatement_flags_from_stored_figures(
    session: Session, tmp_path: Path
) -> None:
    """FR-RF-001: a 10-K whose Beneish score is above -1.78 is flagged (info), and a 10-K/A whose
    as-reported value differs from the original filing's is flagged with both values."""
    from decimal import Decimal

    from app.finance.builder import build_company_metrics
    from app.finance.quality_builder import build_company_earnings_quality
    from app.finance.ratio_builder import build_company_ratios
    from app.models import FinancialMetric

    company = _nvda(session, tmp_path)
    build_company_metrics(session, company)
    build_company_ratios(session, company)
    build_company_earnings_quality(session, company)
    amended = _filing(
        session, company, fixture=None, items=[], accession="0001045810-26-900099",
        filed=date(2026, 4, 1), form="10-K/A",
    )  # fmt: skip
    for accession, value, latest in (
        ("0001045810-26-000021", "1000", False),
        (amended.accession_number, "990", True),
    ):
        session.add(
            FinancialMetric(
                company_id=company.id, period="FY2026", fiscal_year=2026, period_type="FY",
                metric_name="widgets", metric_value=Decimal(value), unit="USD",
                as_reported_accession=accession, is_latest=latest, is_derived=False,
            )
        )  # fmt: skip
    session.flush()
    scan_company(session, company)

    beneish = _flags(session, company, rule_key="beneish_above_threshold")
    assert beneish and all(f.severity == "info" for f in beneish)
    tenk = session.scalars(
        select(Filing).where(Filing.accession_number == "0001045810-26-000021")
    ).one()
    assert any(f.filing_id == tenk.id for f in beneish)
    assert all("screening heuristic, not a finding" in f.snippet for f in beneish)
    [restated] = _flags(session, company, rule_key="restatement_in_xbrl")
    assert restated.filing_id == amended.id and restated.payload is not None
    assert restated.payload["restated"] == [
        {
            "metric": "widgets",
            "period": "FY2026",
            "before": "1000.00000000",
            "after": "990.00000000",
        }
    ]


def test_one_failing_filing_does_not_stop_the_scan(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ING-005: a filing whose evaluation fails is dead-lettered; the others are still flagged."""
    from app.models import IngestionDeadLetter

    company = _nvda(session, tmp_path)
    real = taxonomy.evaluate

    def flaky(
        evidence: taxonomy.FilingEvidence,
    ) -> list[tuple[taxonomy.RedFlagRule, taxonomy.Match]]:
        if evidence.filing_type == "NT 10-Q":
            raise RuntimeError("boom")
        return real(evidence)

    monkeypatch.setattr(taxonomy, "evaluate", flaky)  # the module `detect` calls through
    summary = scan_company(session, company)
    assert summary.failed == 1
    late = _flags(session, company, rule_key="late_filing_notice")
    assert [session.get(Filing, f.filing_id).filing_type for f in late] == ["NT 10-K"]  # type: ignore[union-attr]
    assert session.scalar(
        select(func.count())
        .select_from(IngestionDeadLetter)
        .where(IngestionDeadLetter.source == "red_flags")
    )


def test_malformed_redflag_ids_and_rule_key_filter(session: Session, tmp_path: Path) -> None:
    """FR-RF-008/011: a malformed `redflag:` ID is not found; an alert can narrow to rule keys."""
    company = _nvda(session, tmp_path)
    assert resolve_source(session, "redflag:NVDA:only-two") is None
    user = User(email="keys@example.com", password_hash="x")  # noqa: S106
    session.add(user)
    session.flush()
    narrow = _alert(session, user, company, min_severity="info", rule_keys=["auditor_change"])
    today = datetime.now(UTC).date()
    _filing(
        session,
        company,
        fixture=None,
        items=["4.01"],
        accession="0000000000-26-904031",
        filed=today,
    )
    _filing(
        session,
        company,
        fixture=None,
        items=["4.02"],
        accession="0000000000-26-904032",
        filed=today,
    )
    scan_company(session, company)
    assert check_and_dispatch(session, now=datetime.now(UTC) + timedelta(minutes=2)) == 1
    assert [n.event_key for n in _notes(session, narrow)] == [
        "redflag:NVDA:auditor_change:0000000000-26-904031"
    ]
