"""Alert evaluation tests (OBS-003, ADR-0021). Real Postgres; skips offline.

DoD: "alerts fire correctly in a simulated failure" — each test seeds the exact DB state that
should cross a threshold and asserts `evaluate_alerts` fires (and that healthy state doesn't).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Company, DataFreshness, IngestionRun, Job, LlmCall
from app.observability.alerts import evaluate_alerts


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


def test_no_alerts_on_healthy_state(session: Session) -> None:
    company = Company(ticker="OK", cik="0000000099", name="OK Corp")
    session.add(company)
    session.flush()
    session.add(
        DataFreshness(
            company_id=company.id,
            source="sec",
            status="fresh",
            last_success_at=datetime.now(UTC),
            last_attempt_at=datetime.now(UTC),
        )
    )
    session.flush()
    assert evaluate_alerts(session) == []


def test_ingestion_lag_alert_fires_past_threshold(session: Session) -> None:
    """Force SEC's last successful ingest beyond the 60-minute threshold (DoD example)."""
    settings = get_settings()
    company = Company(ticker="LAG", cik="0000000098", name="Lag Corp")
    session.add(company)
    session.flush()
    stale_at = datetime.now(UTC) - timedelta(minutes=settings.alert_ingestion_lag_minutes + 5)
    session.add(
        DataFreshness(
            company_id=company.id,
            source="sec",
            status="stale",
            last_success_at=stale_at,
            last_attempt_at=datetime.now(UTC),
        )
    )
    session.flush()

    alerts = evaluate_alerts(session)
    assert any(a.name == "ingestion_lag" for a in alerts)


def test_ingestion_lag_alert_silent_when_fresh(session: Session) -> None:
    company = Company(ticker="FRESH", cik="0000000097", name="Fresh Corp")
    session.add(company)
    session.flush()
    session.add(
        DataFreshness(
            company_id=company.id,
            source="sec",
            status="fresh",
            last_success_at=datetime.now(UTC) - timedelta(minutes=5),
            last_attempt_at=datetime.now(UTC),
        )
    )
    session.flush()
    assert not any(a.name == "ingestion_lag" for a in evaluate_alerts(session))


def test_job_failure_spike_alert_fires(session: Session) -> None:
    for _ in range(4):
        session.add(Job(job_type="research_report", status="failed"))
    session.add(Job(job_type="research_report", status="done"))
    session.flush()

    alerts = evaluate_alerts(session)
    assert any(a.name == "job_failure_spike" for a in alerts)


def test_ingestion_failure_spike_alert_fires(session: Session) -> None:
    for _ in range(4):
        session.add(IngestionRun(source="sec", status="failed"))
    session.add(IngestionRun(source="sec", status="success"))
    session.flush()

    alerts = evaluate_alerts(session)
    assert any(a.name == "ingestion_failure_spike" for a in alerts)


def test_llm_spend_over_budget_alert_fires(session: Session) -> None:
    settings = get_settings()
    session.add(
        LlmCall(
            purpose="chat",
            model="claude-sonnet-5-5",
            input_tokens=1,
            cost_usd=settings.llm_daily_budget_usd + Decimal("1.00"),
            latency_ms=1,
            status="success",
        )
    )
    session.flush()

    alerts = evaluate_alerts(session)
    assert any(a.name == "llm_spend_over_budget" for a in alerts)


def test_sec_429_alert_fires_over_threshold(session: Session) -> None:
    settings = get_settings()
    alerts = evaluate_alerts(
        session, recent_sec_429_count=settings.alert_sec_429_count_threshold + 1
    )
    assert any(a.name == "sec_429_repeated" for a in alerts)


def test_sec_429_alert_silent_under_threshold(session: Session) -> None:
    alerts = evaluate_alerts(session, recent_sec_429_count=0)
    assert not any(a.name == "sec_429_repeated" for a in alerts)
