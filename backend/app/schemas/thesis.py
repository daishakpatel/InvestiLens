"""Investment thesis tracker API (Phase 7k, FR-TH-013). Thesis text is the user's own and
private (SEC-TH-002); KPI thresholds and values are Decimals in the metric's canonical unit
(ratios as decimals: 0.25 = 25%)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.filings import DiffOp

Stance = Literal["long", "short", "watch", "avoid"]
ThesisStatus = Literal["active", "closed"]
Comparator = Literal["gte", "lte", "gt", "lt"]
PeriodType = Literal["FY", "Q", "TTM", "LATEST"]
KpiState = Literal["met", "broken", "no_data"]
Unit = Literal["usd", "usd_per_share", "ratio", "multiple", "score", "days"]
EventKind = Literal[
    "kpi_met", "kpi_broken", "red_flag", "brief_published", "user_note", "status_changed"
]

TITLE_MAX = 200
BODY_MAX = 20_000
LABEL_MAX = 120
RATIONALE_MAX = 1_000
NOTE_MAX = 2_000
DRAFT_NOTES_MAX = 5_000


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ThesisCreate(_Strict):
    ticker: str = Field(min_length=1, max_length=12)
    title: str = Field(min_length=1, max_length=TITLE_MAX)
    body_md: str = Field(default="", max_length=BODY_MAX)
    stance: Stance  # the user's own tag; the app never suggests one


class ThesisUpdate(_Strict):
    title: str | None = Field(default=None, min_length=1, max_length=TITLE_MAX)
    body_md: str | None = Field(default=None, max_length=BODY_MAX)
    stance: Stance | None = None
    status: ThesisStatus | None = None


class KpiCreate(_Strict):
    metric: str = Field(min_length=1, max_length=64)
    period_type: PeriodType
    comparator: Comparator
    threshold: Decimal = Field(allow_inf_nan=False)
    label: str = Field(min_length=1, max_length=LABEL_MAX)
    rationale: str | None = Field(default=None, max_length=RATIONALE_MAX)


class KpiUpdate(_Strict):
    metric: str | None = Field(default=None, min_length=1, max_length=64)
    period_type: PeriodType | None = None
    comparator: Comparator | None = None
    threshold: Decimal | None = Field(default=None, allow_inf_nan=False)
    label: str | None = Field(default=None, min_length=1, max_length=LABEL_MAX)
    rationale: str | None = Field(default=None, max_length=RATIONALE_MAX)


class KpiPoint(BaseModel):
    period: str
    period_end: date | None
    value: Decimal
    source_ids: list[str]


class Kpi(BaseModel):
    id: int
    metric: str
    metric_label: str
    unit: Unit
    period_type: PeriodType
    comparator: Comparator
    threshold: Decimal
    label: str
    rationale: str | None
    state: KpiState
    last_value: Decimal | None
    last_source_ids: list[str]
    last_period: str | None
    last_period_end: date | None
    evaluated_at: datetime | None
    history: list[KpiPoint]  # oldest first, for the sparkline (stored rows only)


class StateCounts(BaseModel):
    met: int = 0
    broken: int = 0
    no_data: int = 0


class ThesisSummary(BaseModel):
    id: int
    ticker: str
    title: str
    stance: Stance
    status: ThesisStatus
    created_at: datetime
    updated_at: datetime
    kpi_states: StateCounts


class ThesisDetail(ThesisSummary):
    body_md: str
    kpis: list[Kpi]


class ThesisEvent(BaseModel):
    id: int
    kind: EventKind
    occurred_at: datetime
    kpi_id: int | None
    ref_type: str | None  # metric | red_flag | earnings_brief
    ref_id: str | None  # a backend source ID: opens the evidence
    note: str | None
    payload: dict[str, Any]


class ThesisRevision(BaseModel):
    revision: int
    title: str
    body_md: str
    created_at: datetime
    word_diff: list[DiffOp] | None  # against the previous revision; None for the first


class NoteCreate(_Strict):
    note: str = Field(min_length=1, max_length=NOTE_MAX)


class MetricRegistryEntry(BaseModel):
    key: str
    label: str
    group: str
    unit: Unit
    period_types: list[PeriodType]
    description: str
    applicable: bool | None  # for `ticker`'s sector; None without a ticker


class MetricRegistryResponse(BaseModel):
    version: str
    ticker: str | None
    metrics: list[MetricRegistryEntry]


class DraftRequest(_Strict):
    ticker: str = Field(min_length=1, max_length=12)
    notes: str = Field(min_length=1, max_length=DRAFT_NOTES_MAX)


class DraftKpi(BaseModel):
    metric: str
    metric_label: str
    unit: Unit
    period_type: PeriodType
    comparator: Comparator
    threshold: Decimal  # a starting point the user must edit
    label: str
    rationale: str | None


class DraftResponse(BaseModel):
    """Suggestions only: nothing is saved until the user accepts them. No stance is suggested."""

    title: str | None
    kpis: list[DraftKpi]
    dropped: int  # proposals rejected (unknown metric, bad period or unit, judgement wording)
    prompt_version: str
    notice: str
