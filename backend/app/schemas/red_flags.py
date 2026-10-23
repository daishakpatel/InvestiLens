"""Red-flag panel responses (Phase 7e, FR-RF-009/010)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

Severity = Literal["info", "warning", "critical"]


class RedFlagFiling(BaseModel):
    id: int
    filing_type: str
    accession_number: str
    filing_date: str | None = None
    url: str | None = None  # the filing on EDGAR


class RedFlagItem(BaseModel):
    """One reported event. `label` and `snippet` state what was reported, never a judgement."""

    source_id: str  # `redflag:{TICKER}:{rule_key}:{accession}`, resolvable via /sources/{id}
    ticker: str
    rule_key: str
    label: str
    severity: Severity  # how closely to read it, not how bad it is
    explanation: str  # what the trigger means (e.g. what Item 4.02 is)
    rule_source: str  # the SEC form or standard the trigger comes from
    event_date: str | None  # the filing date, not the detection time
    snippet: str  # the filing's own words
    filing: RedFlagFiling
    details: dict[str, Any] = {}  # item code, roles, going-concern class, restated values, …


class RedFlagsResponse(BaseModel):
    """Empty `items` with a `last_scanned_at` means "scanned through that date, nothing reported";
    `last_scanned_at` is null until the first scan."""

    items: list[RedFlagItem]
    last_scanned_at: datetime | None
    taxonomy_version: str
