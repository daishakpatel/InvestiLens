"""Alert event-type registry (Phase 7a, FR-AL-001..004).

One `AlertEventType` per kind of event a user can be alerted about. Dispatch, the API and the UI
all read this registry, so a new event type is one `register(...)` call next to its detector:
no new query loop, dedupe or form. Detectors are deterministic (no LLM) and return
`DetectedEvent`s whose `event_key` is identical every time the same real-world event is seen,
which is what makes delivery idempotent (`notifications(alert_id, event_key)` is unique).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.models import Alert
from app.repositories import watchlists as watchlist_repo

Severity = Literal["info", "warning", "critical"]


@dataclass(frozen=True)
class DetectedEvent:
    """One real-world event an alert matched. `body` is plain, factual text (no advice, LGL-006);
    `source_ids` are backend-issued (CIT rules), never model-written."""

    event_key: str
    occurred_at: datetime  # UTC
    company_id: int
    title: str
    body: str
    source_ids: tuple[str, ...]
    severity: Severity = "info"


# (session, alert, since, until) -> events with since < occurred_at <= until (FR-AL-002).
Detector = Callable[[Session, Alert, datetime, datetime], list[DetectedEvent]]


class NoParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class AlertEventType:
    key: str
    label: str
    description: str
    params_schema: type[BaseModel]
    detector: Detector
    # What the detector produces for a typical event; checked against the advice guard in tests.
    sample: DetectedEvent
    default_enabled: bool = True


_REGISTRY: dict[str, AlertEventType] = {}


def register(event_type: AlertEventType) -> AlertEventType:
    if event_type.key in _REGISTRY:
        raise ValueError(f"alert event type {event_type.key!r} is already registered")
    _REGISTRY[event_type.key] = event_type
    return event_type


def get(key: str) -> AlertEventType | None:
    return _REGISTRY.get(key)


def all_types() -> list[AlertEventType]:
    return list(_REGISTRY.values())


def scope_company_ids(session: Session, alert: Alert) -> list[int]:
    """The companies an alert covers right now. A watchlist-wide alert (`company_id` NULL) reads
    the watchlist at run time, so a ticker added after the alert was created is covered
    (FR-AL-011)."""
    if alert.company_id is not None:
        return [alert.company_id]
    return watchlist_repo.company_ids_for_user(session, user_id=alert.user_id)
