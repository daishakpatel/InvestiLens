"""The `red_flag` alert event type (Phase 7e, FR-RF-011, ADR-0043).

Fires once per reported event (`event_key` = the flag's source ID) when a scan first detects it.
`occurred_at` is that first detection, so a new taxonomy version or a rescan never re-announces
an event. A flag on a filing dated more than `FRESH_DAYS` before it was detected is history being
backfilled (a new company, a new rule over old filings), not news, and does not alert. Body text
is the neutral template only: "Reported: {label} (filed {date})."
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.alerts.registry import AlertEventType, DetectedEvent, register, scope_company_ids
from app.models import Alert
from app.redflags import taxonomy
from app.repositories import red_flags as repo

FRESH_DAYS = 7


# Every rule key, as a Literal so the alert form offers them as choices (its JSON Schema is an
# enum). A unit test keeps it equal to the taxonomy's keys.
RuleKey = Literal[
    "non_reliance",
    "auditor_change",
    "late_filing_notice",
    "exec_departure",
    "exec_change_unspecified",
    "impairment",
    "restructuring",
    "delisting_notice",
    "bankruptcy",
    "material_cyber_incident",
    "change_in_control",
    "going_concern",
    "going_concern_alleviated",
    "going_concern_risk_language",
    "material_weakness",
    "beneish_above_threshold",
    "restatement_in_xbrl",
]


class RedFlagParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min_severity: Literal["info", "warning", "critical"] = Field(
        default="warning",
        title="Minimum severity",
        description="Only flags at or above this: info < warning < critical.",
    )
    rule_keys: list[RuleKey] | None = Field(
        default=None,
        title="Flag types",
        description="Only these flag types. Leave empty for all.",
    )


def red_flag_event(
    *,
    ticker: str,
    rule_key: str,
    accession: str,
    company_id: int,
    filed: date | None,
    at: datetime,
) -> DetectedEvent:
    rule = taxonomy.RULES_BY_KEY[rule_key]
    sid = taxonomy.source_id(ticker, rule_key, accession)
    return DetectedEvent(
        event_key=sid,
        occurred_at=at,
        company_id=company_id,
        title=f"{ticker}: {rule.label}",
        body=f"Reported: {rule.label} (filed {filed.isoformat() if filed else 'date unknown'}).",
        source_ids=(sid,),
        severity=rule.severity,
    )


def detect_red_flags(
    session: Session, alert: Alert, since: datetime, until: datetime
) -> list[DetectedEvent]:
    params = RedFlagParams.model_validate(alert.params)
    rows = repo.latest_flags(
        session,
        company_ids=scope_company_ids(session, alert),
        taxonomy_version=taxonomy.TAXONOMY_VERSION,
        severities=taxonomy.severities_at_least(params.min_severity),
        rule_keys=list(params.rule_keys or []),
        detected_after=since,
        detected_until=until,
    )
    events = []
    for flag, filing, ticker in rows:
        fresh = flag.event_date is None or flag.event_date >= (
            flag.detected_at.date() - timedelta(days=FRESH_DAYS)
        )
        if fresh and flag.rule_key in taxonomy.RULES_BY_KEY:
            events.append(
                red_flag_event(
                    ticker=ticker,
                    rule_key=flag.rule_key,
                    accession=filing.accession_number,
                    company_id=flag.company_id,
                    filed=flag.event_date,
                    at=flag.detected_at,
                )
            )
    return events


register(
    AlertEventType(
        key="red_flag",
        label="Red flag",
        description="A filing reports an event such as an auditor change, a non-reliance notice, "
        "a late filing or an executive departure.",
        params_schema=RedFlagParams,
        detector=detect_red_flags,
        sample=red_flag_event(
            ticker="NVDA",
            rule_key="non_reliance",
            accession="0001045810-26-000099",
            company_id=1,
            filed=date(2026, 1, 15),
            at=datetime(2026, 1, 15, 21, 0, tzinfo=UTC),
        ),
    )
)
