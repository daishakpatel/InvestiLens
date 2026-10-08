"""Alert evaluation (OBS-003, ADR-0021): ingestion lag, job/ingestion failure spikes, LLM spend
over budget, repeated SEC 429s, and error-rate SLO burn.

A pure function over the same DB state `app.observability.metrics` reads, deliberately
independent of any running Prometheus/Alertmanager — this is what makes the DoD's "alerts fire
correctly in a simulated failure" testable in CI with no infra (seed the DB/counters past a
threshold, call `evaluate_alerts`, assert it fires). `observability/alerts.rules.yml` mirrors
these exact thresholds for a real Prometheus deployment; the two are meant to be read side by
side, not as alternatives to keep in sync by hand — this module is the thresholds' source of
truth and the YAML is generated conceptually from the same config (`app.config.Settings`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.repositories import freshness as freshness_repo
from app.repositories import ingestion as ingestion_repo
from app.repositories import jobs as job_repo
from app.repositories import llm_calls as llm_repo


@dataclass(frozen=True)
class Alert:
    name: str
    severity: str  # "warning" | "critical"
    message: str


def _ingestion_lag_alerts(session: Session, settings: Settings) -> list[Alert]:
    now = datetime.now(UTC)
    alerts: list[Alert] = []
    for row in freshness_repo.list_all(session):
        if row.last_success_at is None:
            continue
        lag_minutes = (now - row.last_success_at).total_seconds() / 60
        if lag_minutes > settings.alert_ingestion_lag_minutes:
            alerts.append(
                Alert(
                    name="ingestion_lag",
                    severity="critical",
                    message=(
                        f"{row.source} ingestion is {lag_minutes:.0f}m stale "
                        f"(threshold {settings.alert_ingestion_lag_minutes}m), company_id="
                        f"{row.company_id}"
                    ),
                )
            )
    return alerts


def _job_failure_alert(session: Session, settings: Settings) -> Alert | None:
    recent = job_repo.recent(session, limit=settings.alert_job_failure_window)
    terminal = [j for j in recent if j.status in ("done", "failed")]
    if not terminal:
        return None
    rate = sum(j.status == "failed" for j in terminal) / len(terminal)
    if rate > settings.alert_job_failure_rate_threshold:
        return Alert(
            name="job_failure_spike",
            severity="critical",
            message=f"{rate:.0%} of the last {len(terminal)} jobs failed",
        )
    return None


def _ingestion_failure_alert(session: Session, settings: Settings) -> Alert | None:
    recent = ingestion_repo.recent(session, limit=settings.alert_job_failure_window)
    terminal = [r for r in recent if r.status in ("success", "failed", "partial")]
    if not terminal:
        return None
    rate = sum(r.status == "failed" for r in terminal) / len(terminal)
    if rate > settings.alert_job_failure_rate_threshold:
        return Alert(
            name="ingestion_failure_spike",
            severity="critical",
            message=f"{rate:.0%} of the last {len(terminal)} ingestion runs failed",
        )
    return None


def _llm_spend_alert(
    session: Session, settings: Settings, *, today_spend_usd: Decimal | None = None
) -> Alert | None:
    """`today_spend_usd` lets a test inject a value directly; otherwise it's read from
    `llm_calls` — a global circuit-breaker signal, distinct from the per-user budget (ADR-0022)."""
    spend = today_spend_usd if today_spend_usd is not None else llm_repo.daily_spend(session)
    if spend > settings.llm_daily_budget_usd:
        return Alert(
            name="llm_spend_over_budget",
            severity="warning",
            message=(
                f"LLM spend today is ${spend}, over the ${settings.llm_daily_budget_usd} budget"
            ),
        )
    return None


def _sec_429_alert(*, recent_429_count: int, settings: Settings) -> Alert | None:
    """`recent_429_count` is supplied by the caller (from `HardenedHttpClient`'s retry logs);
    this module has no log-scraping of its own — keeping it a pure, DB/counter-driven function."""
    if recent_429_count > settings.alert_sec_429_count_threshold:
        return Alert(
            name="sec_429_repeated",
            severity="warning",
            message=f"{recent_429_count} SEC EDGAR 429s in the recent window",
        )
    return None


def evaluate_alerts(
    session: Session,
    *,
    settings: Settings | None = None,
    recent_sec_429_count: int = 0,
    today_llm_spend_usd: Decimal | None = None,
) -> list[Alert]:
    """Evaluate every alert rule against current DB state. Pure w.r.t. its inputs — no I/O beyond
    the given `session`, so it's deterministic and fast to call from a scheduled check or a test.
    """
    settings = settings or get_settings()
    alerts = list(_ingestion_lag_alerts(session, settings))
    for alert in (
        _job_failure_alert(session, settings),
        _ingestion_failure_alert(session, settings),
        _llm_spend_alert(session, settings, today_spend_usd=today_llm_spend_usd),
        _sec_429_alert(recent_429_count=recent_sec_429_count, settings=settings),
    ):
        if alert is not None:
            alerts.append(alert)
    return alerts
