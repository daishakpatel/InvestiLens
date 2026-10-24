"""Governance responses (Phase 7g, FR-GV-011). Every missing part is an explicit null with a
`reason`, never an empty value that could be read as zero."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.schemas.filings import FilingSummary


class GovernanceField(BaseModel):
    """One Tier C field. `value` null = "not stated" (absent, or failed verification)."""

    name: str
    label: str
    value: Decimal | bool | list[str] | None = None
    quote: str | None = None  # verbatim from the proxy
    paragraph_id: str | None = None  # resolvable via /sources/{id}


class BoardFacts(BaseModel):
    """AI-extracted (marked as such in the UI). `independence_ratio` is computed in code from the
    two verified counts, as a decimal (0.9167 = 91.67%)."""

    status: Literal["extracted", "pending", "no_sections"]
    model: str | None = None
    fields: list[GovernanceField] = []
    independence_ratio: Decimal | None = None
    reason: str | None = None


class CompensationRow(BaseModel):
    person: str  # name and position as printed
    role: Literal["peo", "pfo", "neo"]
    fiscal_year: int
    components: dict[str, Decimal]  # salary, bonus, stock_awards, …; absent column = absent key
    total: Decimal
    source_id: str  # the Summary Compensation Table chunk


class Compensation(BaseModel):
    """Tier B: rows that add up to their total; the rest were rejected, never repaired."""

    rows: list[CompensationRow] = []
    rejected_rows: int = 0
    reason: str | None = None


class PayVersusPerformancePoint(BaseModel):
    fiscal_year: int
    values: dict[str, Decimal]  # peo_total_comp, peo_actually_paid_comp, tsr, peer_group_tsr, …
    source_ids: dict[str, str]  # same keys -> xbrl:<financial_facts.id>


class PayVersusPerformance(BaseModel):
    """Tier A, from the proxy's Inline XBRL. TSR values are the worth of $100 invested."""

    points: list[PayVersusPerformancePoint] = []
    company_selected_measure: str | None = None
    reason: str | None = None


class PayRatio(BaseModel):
    ratio: Decimal | None = None  # CEO pay as a multiple of the median employee's ("363" = 363:1)
    median_pay: Decimal | None = None
    ceo_total: Decimal | None = None  # the Summary Compensation Table total it was checked against
    source_id: str | None = None
    reason: str | None = None


class GovernanceResponse(BaseModel):
    company_ticker: str
    fiscal_year: int | None  # the year the proxy covers, from its content (not its filing date)
    fiscal_year_source: str | None  # pay_versus_performance_xbrl | summary_compensation_table
    filing: FilingSummary | None
    available_years: list[int]
    proxies_ingested: int  # DEF 14A filings stored for the company, processed or not
    reason: str | None = None  # why nothing is shown, when `filing` is null
    coverage: dict[str, bool] = {}  # proxy section -> found
    facts: BoardFacts | None = None
    compensation: Compensation | None = None
    pay_vs_performance: PayVersusPerformance | None = None
    pay_ratio: PayRatio | None = None


class GovernanceHistoryPoint(BaseModel):
    fiscal_year: int
    ceo_total_pay: Decimal | None = None
    ceo_total_pay_source: str | None = None  # summary_compensation_table | pay_versus_performance
    ceo_total_pay_source_id: str | None = None
    independence_ratio: Decimal | None = None


class GovernanceHistoryResponse(BaseModel):
    company_ticker: str
    points: list[GovernanceHistoryPoint]
