"""Alert dispatch (§26.2, Phase 5d DoD). Real Postgres; skips offline.

The DoD: "alert dispatch actually sends a notification within 30 minutes of a simulated
triggering event (e.g. a test filing ingestion)." These seed the triggering event, run
`check_and_dispatch`, and assert a notification is produced — plus idempotency (a second run with
no new event sends nothing) and the in-app read path (`GET /notifications`).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.alerts.dispatch import check_and_dispatch
from app.db import get_db
from app.main import app
from app.models import Alert, Company, Document, Filing, Notification, PriceHistory, User
from app.notifications.sender import EmailBackend, NotificationSender
from tests.fakes import auth_headers


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


def _company(session: Session, ticker: str = "TST") -> Company:
    company = Company(ticker=ticker, cik="0000000011", name="Test Corp")
    session.add(company)
    session.flush()
    return company


def _user(session: Session, email: str = "alerts@example.com") -> User:
    user = User(email=email, password_hash="x")  # noqa: S106
    session.add(user)
    session.flush()
    return user


def _ingest_8k(session: Session, company: Company) -> None:
    doc = Document(company_id=company.id, document_type="filing", source_tier=1, content_hash="8k1")
    session.add(doc)
    session.flush()
    session.add(
        Filing(
            document_id=doc.id,
            company_id=company.id,
            filing_type="8-K",
            filing_date=date(2026, 10, 8),
            accession_number="0000000011-26-000001",
        )
    )
    session.flush()


def test_new_filing_dispatches_notification(session: Session) -> None:
    company = _company(session)
    user = _user(session)
    session.add(
        Alert(user_id=user.id, company_id=company.id, alert_type="new_8k", channel="in_app")
    )
    session.flush()
    _ingest_8k(session, company)  # the triggering event

    sent = check_and_dispatch(session)
    assert sent == 1
    notif = session.scalars(select(Notification).where(Notification.user_id == user.id)).one()
    assert notif.channel == "in_app" and "8-K" in notif.title

    # Idempotent: a second run with no new filing sends nothing (watermark advanced).
    assert check_and_dispatch(session) == 0


def test_price_move_dispatches_when_over_threshold(session: Session) -> None:
    company = _company(session, "MOV")
    user = _user(session, "mover@example.com")
    session.add(
        Alert(
            user_id=user.id,
            company_id=company.id,
            alert_type="price_move",
            channel="in_app",
            config={"threshold": 0.05},
        )
    )
    now = datetime.now(UTC)
    session.add_all(
        [
            PriceHistory(
                company_id=company.id,
                date=date(2026, 10, 7),
                close=Decimal("100.00"),
                provider="mock",
                ingested_at=now - timedelta(days=1),
            ),
            PriceHistory(
                company_id=company.id,
                date=date(2026, 10, 8),
                close=Decimal("110.00"),
                provider="mock",
                ingested_at=now,
            ),
        ]
    )
    session.flush()

    sent = check_and_dispatch(session)
    assert sent == 1
    notif = session.scalars(select(Notification).where(Notification.user_id == user.id)).one()
    assert "+10" in notif.title or "10" in notif.title


def test_email_channel_invokes_email_backend(session: Session) -> None:
    company = _company(session, "EML")
    user = _user(session, "emailme@example.com")
    session.add(Alert(user_id=user.id, company_id=company.id, alert_type="new_8k", channel="email"))
    session.flush()
    _ingest_8k(session, company)

    captured: list[tuple[str, str]] = []

    class _CapturingBackend(EmailBackend):
        def send(self, *, to: str, subject: str, body: str) -> None:
            captured.append((to, subject))

    sender = NotificationSender(email_backend=_CapturingBackend())
    assert check_and_dispatch(session, sender=sender) == 1
    assert captured and captured[0][0] == "emailme@example.com"  # email delivery attempted


def test_notifications_endpoint_returns_dispatched(session: Session) -> None:
    company = _company(session, "API")
    user = _user(session, "apiuser@example.com")
    session.add(
        Alert(user_id=user.id, company_id=company.id, alert_type="new_8k", channel="in_app")
    )
    session.flush()
    _ingest_8k(session, company)
    check_and_dispatch(session)

    app.dependency_overrides[get_db] = lambda: session
    try:
        client = TestClient(app)
        resp = client.get("/api/v1/notifications", headers=auth_headers(user.id))
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1 and "8-K" in body[0]["title"] and body[0]["read"] is False
    finally:
        app.dependency_overrides.clear()
