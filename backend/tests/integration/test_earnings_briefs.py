"""Earnings calendar, previews, briefs, versions, alerts and API (Phase 7j). Real Postgres, mock
SEC and prices (the frozen NVDA fixtures).

Requirement IDs: FR-EB-001..009, FR-EB-012/013, DR-PS-001 (bands omitted), CIT-EB-001.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from app.alerts.dispatch import check_and_dispatch
from app.api import earnings as earnings_api
from app.api.deps import get_current_user
from app.api.rate_limit_backends import MemoryRateLimiter
from app.config import get_settings
from app.db import get_db
from app.earnings import calendar, service
from app.filings.service import _units
from app.finance.builder import build_company_metrics
from app.finance.ratio_builder import build_company_ratios
from app.guidance import extract
from app.guidance.builder import build_company_guidance
from app.ingestion.documents.chunker import PARSER_VERSION
from app.ingestion.documents.pipeline import parse_company_documents
from app.ingestion.prices import ingest_prices
from app.ingestion.sec import ingest_company
from app.main import app
from app.models import (
    Alert,
    Company,
    Document,
    DocumentChunk,
    EarningsBrief,
    Filing,
    Notification,
    User,
    ValuationHistory,
    Watchlist,
    WatchlistItem,
)
from app.providers.prices.mock import MockPriceSource
from app.providers.sec.base import FilingRef
from app.providers.sec.mock import MockSecSource
from app.redflags.detect import scan_company
from app.utils.storage import FilesystemObjectStorage
from tests.integration.test_guidance import _Recorded

_P = "/api/v1"
_TODAY = date(2026, 9, 15)
_ANNOUNCEMENT = (
    "NVIDIA will report its financial results for the third quarter of fiscal 2027 after the "
    "market closes on Wednesday, November 18, 2026."
)


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


class _Without10Q(MockSecSource):
    """The fixture filings as of the earnings release, before the 10-Q is filed."""

    def list_filings(self, cik: str, *, since: date | None = None) -> Sequence[FilingRef]:
        return [f for f in super().list_filings(cik, since=since) if f.form != "10-Q"]


def _ingest(session: Session, storage: FilesystemObjectStorage, sec: MockSecSource) -> Company:
    ingest_company(session, "NVDA", sec=sec, storage=storage)
    company = session.scalars(select(Company).where(Company.ticker == "NVDA")).one()
    parse_company_documents(session, company.id, storage=storage)
    build_company_metrics(session, company)
    return company


def _nvda(session: Session, tmp_path: Path, *, with_10q: bool = True) -> Company:
    """NVDA as production builds it: filings, metrics, prices (valuation + bands), red flags and
    guidance from the recorded extraction of the Q2 FY2027 release."""
    storage = FilesystemObjectStorage(tmp_path)
    company = _ingest(session, storage, MockSecSource() if with_10q else _Without10Q())
    build_company_ratios(session, company)
    ingest_prices(session, company, source=MockPriceSource())
    scan_company(session, company)
    release = session.scalars(
        select(Document).where(
            Document.company_id == company.id,
            Document.document_type == "earnings_release",
            Document.doc_metadata["exhibit_type"].astext == "EX-99.1",
        )
    ).one()
    extract.extract_document_guidance(session, release, company, llm=_Recorded())
    build_company_guidance(session, company)
    return company


def _add_8k(session: Session, company: Company, day: date, accession: str) -> Filing:
    doc = Document(
        company_id=company.id,
        document_type="filing",
        source_tier=1,
        content_hash=accession,
        parser_version=PARSER_VERSION,
    )
    session.add(doc)
    session.flush()
    filing = Filing(
        document_id=doc.id,
        company_id=company.id,
        filing_type="8-K",
        filing_date=day,
        period_end=day,
        accession_number=accession,
        items=["2.02", "9.01"],
    )
    session.add(filing)
    session.flush()
    return filing


def _announce(session: Session, company: Company, text: str, filed: date) -> None:
    filing = _add_8k(session, company, filed, "0001045810-26-000099")
    filing.items = ["7.01", "9.01"]  # an announcement, not an earnings release
    session.add(
        DocumentChunk(
            document_id=filing.document_id,
            company_id=company.id,
            chunk_index=0,
            chunk_type="text",
            text=text,
            section="Item 7.01",
            section_path=["Item 7.01"],
            paragraph_id=f"{filing.document_id}_7.01_0",
            tier=1,
            filing_type="8-K",
            filing_date=filed,
            parser_version=PARSER_VERSION,
        )
    )
    session.flush()


def _earlier_10q(session: Session, company: Company) -> Filing:
    """A Q1 FY2027 10-Q: the fixture 10-Q's own chunks minus one risk factor, so the real 10-Q
    adds that risk factor (the fixtures hold only one 10-Q)."""
    ten_q = session.scalars(
        select(Filing).where(Filing.company_id == company.id, Filing.filing_type == "10-Q")
    ).one()
    # Guessed captions, matching the diff below: the synthetic filing has no raw HTML of its own,
    # so the diff cannot use bold captions for it whatever the default object store holds.
    units = _units(session, ten_q, styled=False) or []
    owned = [
        set(u.source_ids) - {sid for other in units if other is not u for sid in other.source_ids}
        for u in units
        if u.kind == "risk_factor"
    ]
    dropped = next((ids for ids in owned if ids), set())
    assert dropped, "the fixture 10-Q must have a risk factor of its own chunks"
    original = session.get(Document, ten_q.document_id)
    assert original is not None
    doc = Document(
        company_id=company.id,
        document_type="filing",
        source_tier=1,
        content_hash="earlier-10q",
        parser_version=PARSER_VERSION,
        raw_document_location=original.raw_document_location,
    )
    session.add(doc)
    session.flush()
    earlier = Filing(
        document_id=doc.id,
        company_id=company.id,
        filing_type="10-Q",
        filing_date=date(2026, 5, 20),
        period_end=date(2026, 4, 26),
        accession_number="0001045810-26-000050",
        raw_document_location=None,  # no raw HTML: the diff compares guessed captions
    )
    session.add(earlier)
    prefix = f"{ten_q.document_id}_"
    for chunk in session.scalars(
        select(DocumentChunk).where(DocumentChunk.document_id == ten_q.document_id)
    ):
        if chunk.paragraph_id in dropped:
            continue
        session.add(
            DocumentChunk(
                document_id=doc.id,
                company_id=company.id,
                chunk_index=chunk.chunk_index,
                chunk_type=chunk.chunk_type,
                text=chunk.text,
                section=chunk.section,
                subsection=chunk.subsection,
                section_path=chunk.section_path,
                paragraph_id=f"{doc.id}_{(chunk.paragraph_id or '').removeprefix(prefix)}",
                tier=chunk.tier,
                filing_type="10-Q",
                filing_date=earlier.filing_date,
                parser_version=chunk.parser_version,
                chunk_metadata=chunk.chunk_metadata,
            )
        )
    session.flush()
    return earlier


def _user(session: Session, email: str = "briefs@example.com") -> User:
    user = User(email=email, password_hash="x")  # noqa: S106
    session.add(user)
    session.flush()
    return user


def _brief_alert(session: Session, company: Company) -> Alert:
    alert = Alert(
        user_id=_user(session).id,
        company_id=company.id,
        event_type="brief_ready",
        params={},
        # Rows of one test transaction share now(): the watermark must be strictly earlier.
        watermark_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    session.add(alert)
    session.flush()
    return alert


def _notes(session: Session, alert: Alert) -> list[Notification]:
    return list(session.scalars(select(Notification).where(Notification.alert_id == alert.id)))


def _dispatch(session: Session, minutes: int = 2) -> int:
    return check_and_dispatch(session, now=datetime.now(UTC) + timedelta(minutes=minutes))


# --- calendar (FR-EB-001/002) -------------------------------------------------------------------


def test_calendar_reports_8k_dates_and_estimates_the_next_quarter(
    session: Session, tmp_path: Path
) -> None:
    company = _ingest(session, FilesystemObjectStorage(tmp_path), MockSecSource())
    events = calendar.build_calendar(session, company)
    reported = calendar.latest_reported(events)
    assert reported is not None
    assert (reported.fiscal_year, reported.fiscal_period) == (2027, "Q2")
    assert reported.report_date == date(2026, 8, 26) and reported.source == "sec_8k"
    filing = session.scalars(
        select(Filing).where(Filing.accession_number == "0001045810-26-000073")
    ).one()
    assert reported.source_id == f"filing:{filing.id}"
    # No year-ago release in the fixtures: the next quarter's date is unknown, not guessed.
    upcoming = calendar.upcoming_event(events)
    assert upcoming is not None
    assert (upcoming.fiscal_year, upcoming.fiscal_period, upcoming.status) == (
        2027,
        "Q3",
        "unknown",
    )
    assert upcoming.report_date is None

    _add_8k(session, company, date(2025, 11, 19), "0001045810-25-000200")  # Q3 FY2026 release
    upcoming = calendar.upcoming_event(calendar.build_calendar(session, company))
    assert upcoming is not None
    assert (upcoming.source, upcoming.status) == ("estimated", "scheduled")
    assert upcoming.report_date == date(2026, 11, 18)  # 52 weeks on: also a Wednesday

    _announce(session, company, f"Intro. {_ANNOUNCEMENT}", date(2026, 9, 3))
    events = calendar.build_calendar(session, company)
    upcoming = calendar.upcoming_event(events)
    assert upcoming is not None
    assert (upcoming.source, upcoming.report_time, upcoming.quote) == (
        "announcement",
        "amc",
        _ANNOUNCEMENT,
    )
    assert upcoming.source_id and upcoming.source_id.endswith("_7.01_0")
    # Idempotent: one row per quarter however often it runs.
    assert len(calendar.build_calendar(session, company)) == len(events)


# --- DoD: an estimated date never produces a "preview ready" notification -----------------------


def test_estimated_dates_never_notify(session: Session, tmp_path: Path) -> None:
    company = _nvda(session, tmp_path)
    _add_8k(session, company, date(2025, 11, 19), "0001045810-25-000200")
    alert = _brief_alert(session, company)

    # The beat task skips an estimated date even inside the lead window...
    assert service.due_previews(session, [company], today=date(2026, 11, 16)) == 0
    # ...and a preview a user asks for on an estimated date is stored but never notified.
    row, created = service.generate(session, company, "preview", today=_TODAY)
    assert created and row.report_date_estimated
    assert row.content["header"]["date_estimated"] is True
    assert _dispatch(session) == 0 and _notes(session, alert) == []

    # Once the company states the date, the beat makes a preview and it notifies, once.
    _announce(session, company, _ANNOUNCEMENT, date(2026, 9, 3))
    assert service.due_previews(session, [company], today=date(2026, 11, 16)) == 1
    assert service.due_previews(session, [company], today=date(2026, 11, 10)) == 0  # too early
    latest = session.scalars(
        select(EarningsBrief).order_by(EarningsBrief.version.desc()).limit(1)
    ).one()
    assert latest.version == 2 and not latest.report_date_estimated
    # One test transaction shares now(): the later version gets a later timestamp explicitly.
    latest.created_at = datetime.now(UTC) + timedelta(minutes=3)
    session.flush()
    assert _dispatch(session, minutes=4) == 1
    [note] = _notes(session, alert)
    assert note.event_key == "brief_ready:NVDA:2027:Q3:preview"
    assert (note.payload or {})["source_ids"] == [f"earnings_brief:{latest.id}"]
    assert _dispatch(session, minutes=6) == 0


# --- DoD: the NVDA preview, with and without 7h data --------------------------------------------


def test_preview_has_snapshot_guidance_flags_and_valuation(
    session: Session, tmp_path: Path
) -> None:
    company = _nvda(session, tmp_path)
    event = calendar.upcoming_event(calendar.build_calendar(session, company))
    assert event is not None
    preview = service.assemble_preview(session, company, event, today=date(2026, 7, 20))
    snapshot = preview.last_quarter_snapshot
    assert snapshot is not None and snapshot.period_label == "Q2 FY2027"
    rows = {r.metric: r for r in snapshot.rows}
    assert rows["revenue"].value is not None and rows["revenue"].source_ids
    assert rows["revenue"].change_vs_prior_year is not None
    assert (
        rows["gross_margin"].change_kind == "points" and len(rows["gross_margin"].source_ids) == 2
    )
    # Guidance the Q2 release gave for Q3 FY2027 (7i), each with its quote's source ID.
    assert {g.metric for g in preview.guidance_for_period} >= {"revenue"}
    assert all(g.fiscal_period == "Q3" and g.source_id for g in preview.guidance_for_period)
    assert preview.open_flags and all(
        f.source_id.startswith("redflag:") for f in preview.open_flags
    )
    assert preview.valuation_snapshot is not None
    assert {line.multiple for line in preview.valuation_snapshot.lines} <= {"pe_ratio", "ev_ebitda"}
    assert all(line.source_ids for line in preview.valuation_snapshot.lines)
    assert "valuation_snapshot" not in {m.section for m in preview.missing}

    # Without the 7h bands the preview still renders and says what is left out.
    session.execute(delete(ValuationHistory).where(ValuationHistory.company_id == company.id))
    bare = service.assemble_preview(session, company, event, today=date(2026, 7, 20))
    assert bare.valuation_snapshot is None
    assert {m.section: m.reason for m in bare.missing}["valuation_snapshot"] == (
        "Valuation bands are not built for this company."
    )
    assert bare.last_quarter_snapshot == snapshot


def test_watch_items_come_only_from_candidates(session: Session, tmp_path: Path) -> None:
    """FR-EB-005: a company with no quarters and no filings has no candidates, so no items."""
    empty = Company(ticker="EMPT", cik="0000000077", name="Empty Corp")
    session.add(empty)
    session.flush()
    from app.earnings.watch import watch_items

    assert watch_items(session, empty, None) == []
    assert watch_items(session, empty, (2027, "Q2")) == []
    company = _nvda(session, tmp_path)
    for item in watch_items(session, company, (2027, "Q2")):
        assert item.source_ids and not item.reworded


# --- DoD: v1 on the 8-K + EX-99.1 states "10-Q not yet filed"; the 10-Q makes v2 ----------------


def test_brief_versions_follow_the_filings(session: Session, tmp_path: Path) -> None:
    company = _nvda(session, tmp_path, with_10q=False)
    alert = _brief_alert(session, company)

    first = service.after_filings(session, company)
    assert first is not None and first.version == 1 and first.kind == "brief"
    assert first.inputs_label == "after earnings release"
    v1 = service.to_stored(first).brief
    assert v1 is not None and v1.what_changed is None
    assert {m.section: m.reason for m in v1.missing}["what_changed"] == "10-Q not yet filed."
    assert v1.reaction is not None and v1.reaction.source_ids[0].startswith("filing:")
    assert v1.narrative is None  # the mock model writes no verifiable sentence
    assert "narrative" in {m.section for m in v1.missing}

    # Same inputs: the stored version, no new row (idempotent).
    again, created = service.generate(session, company, "brief")
    assert (again.id, created) == (first.id, False)
    assert service.after_filings(session, company) == first

    # The 10-Q lands (and an earlier one to compare it with): version 2, with real diff content.
    storage = FilesystemObjectStorage(tmp_path)
    ingest_company(session, "NVDA", sec=MockSecSource(), storage=storage)
    parse_company_documents(session, company.id, storage=storage)
    _earlier_10q(session, company)
    second = service.after_filings(session, company)
    assert second is not None and second.version == 2 and second.inputs_label == "after 10-Q filed"
    v2 = service.to_stored(second).brief
    assert v2 is not None and v2.what_changed is not None
    assert v2.what_changed.new_risks >= 1
    new = [c for c in v2.what_changed.top_changes if c.status == "new"]
    assert new and new[0].new_quote and new[0].old_quote is None and new[0].source_ids
    assert "what_changed" not in {m.section for m in v2.missing}
    # The old version is kept for audit.
    versions = session.scalars(
        select(EarningsBrief.version).where(EarningsBrief.company_id == company.id)
    ).all()
    assert sorted(versions) == [1, 2]
    # Headline figures are the stored rows with their sources; no number came from a model.
    assert v2.headline_table is not None
    for row in v2.headline_table.rows:
        assert (row.value is None) == (row.reason is not None)
        assert row.value is None or row.source_ids

    # FR-EB-009: one notification per (company, period, kind), across both versions.
    assert _dispatch(session) == 1
    [note] = _notes(session, alert)
    assert note.event_key == "brief_ready:NVDA:2027:Q2:brief"
    assert _dispatch(session, minutes=5) == 0


# --- cost guard (FR-EB-012) ---------------------------------------------------------------------


def test_only_watched_or_seed_companies_and_a_daily_cap(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    company = _nvda(session, tmp_path)
    settings = get_settings()
    monkeypatch.setattr(settings, "earnings_brief_seed_tickers", [])
    with pytest.raises(service.BriefUnavailable) as err:
        service.generate(session, company, "brief")
    assert err.value.code == "not_covered"
    assert service.try_generate(session, company, "brief") is None

    user = _user(session)
    watchlist = Watchlist(user_id=user.id, name="NVDA")
    session.add(watchlist)
    session.flush()
    session.add(WatchlistItem(watchlist_id=watchlist.id, company_id=company.id))
    session.flush()
    monkeypatch.setattr(settings, "earnings_brief_daily_cap", 0)
    capsys.readouterr()
    with pytest.raises(service.BriefUnavailable) as err:
        service.generate(session, company, "brief")
    assert err.value.code == "daily_cap"
    assert "earnings.daily_cap_reached" in capsys.readouterr().out
    monkeypatch.setattr(settings, "earnings_brief_daily_cap", 50)
    assert service.generate(session, company, "brief")[1] is True


# --- API (FR-EB-013) ----------------------------------------------------------------------------


@pytest.fixture
def client(session: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(session, "commit", session.flush)
    app.dependency_overrides[get_db] = lambda: session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_api_calendar_briefs_and_rate_limited_regeneration(
    session: Session, tmp_path: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    company = _nvda(session, tmp_path)
    _add_8k(session, company, date(2025, 11, 19), "0001045810-25-000200")
    resp = client.get(f"{_P}/companies/nvda/earnings/calendar")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["upcoming"]["period_label"] == "Q3 FY2027" and body["upcoming"]["estimated"]
    assert body["events"][1]["source"] == "sec_8k"

    assert client.get(f"{_P}/companies/NVDA/earnings/briefs").json()["items"] == []
    assert (
        client.post(f"{_P}/companies/NVDA/earnings/briefs", json={"kind": "brief"}).status_code
        == 401
    )

    user = _user(session, "api-briefs@example.com")
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(earnings_api, "_regenerations", MemoryRateLimiter())
    monkeypatch.setattr(get_settings(), "earnings_brief_regen_per_hour", 2)
    first = client.post(f"{_P}/companies/NVDA/earnings/briefs", json={"kind": "brief"})
    assert first.status_code == 200, first.text
    assert first.json()["created"] is True and first.json()["item"]["version"] == 1
    again = client.post(f"{_P}/companies/NVDA/earnings/briefs", json={"kind": "brief"})
    assert (
        again.json()["created"] is False
        and again.json()["item"]["id"] == first.json()["item"]["id"]
    )
    limited = client.post(f"{_P}/companies/NVDA/earnings/briefs", json={"kind": "brief"})
    assert limited.status_code == 429 and "limit" in limited.json()["detail"]
    assert (
        client.post(f"{_P}/companies/NVDA/earnings/briefs", json={"kind": "nope"}).status_code
        == 422
    )

    listed = client.get(f"{_P}/companies/NVDA/earnings/briefs", params={"kind": "brief"}).json()
    [item] = listed["items"]
    assert item["kind"] == "brief" and item["brief"]["header"]["period_label"] == "Q2 FY2027"
    assert item["preview"] is None
    assert (
        client.get(
            f"{_P}/companies/NVDA/earnings/briefs", params={"fiscal_period": "Q9"}
        ).status_code
        == 422
    )
    assert session.scalar(select(func.count()).select_from(EarningsBrief)) == 1


def test_api_regeneration_refuses_an_uncovered_company(
    session: Session, tmp_path: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _nvda(session, tmp_path)
    user = _user(session, "uncovered@example.com")
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(earnings_api, "_regenerations", MemoryRateLimiter())
    monkeypatch.setattr(get_settings(), "earnings_brief_seed_tickers", [])
    resp = client.post(f"{_P}/companies/NVDA/earnings/briefs", json={"kind": "preview"})
    assert resp.status_code == 409 and "watchlist" in resp.json()["detail"]
