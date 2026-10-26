"""The metrics a thesis KPI may track, and how each one's values are read (FR-TH-002/005/006).

A fixed, curated list: stored `financial_metrics` rows (annual, 7b quarterly/TTM, 7d scores, 7h
multiples at the latest close), quarterly margins computed from one quarter's rows the way 7i
does, revenue growth year over year, and revenue against its guided midpoint (7i). Each entry has
one canonical unit (ratios as decimals) and the period types it exists for. A value always comes
with the source IDs the rest of the app cites for it; this module never invents a value.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from app.finance.concept_map import load_concept_map
from app.finance.display import format_metric_value
from app.guidance.outcomes import actual_for
from app.guidance.service import grouped, period_label
from app.models import Company
from app.repositories import guidance as guidance_repo
from app.repositories import metrics as metric_repo

Unit = Literal["usd", "usd_per_share", "ratio", "multiple", "score", "days"]
Reader = Literal["stored", "revenue_yoy", "guidance"]
REGISTRY_VERSION = "thesis_metric_registry_v1"
_RATIO_BOUND = Decimal(5)  # a ratio past ±5 (500%) is almost surely a percent typed as a number


@dataclass(frozen=True)
class TrackedMetric:
    key: str
    label: str
    group: str
    unit: Unit
    period_types: tuple[str, ...]
    description: str
    bounds: tuple[Decimal, Decimal] | None = None  # plausible thresholds (unit-mistake guard)
    reader: Reader = "stored"
    applies_as: str | None = None  # concept-map metric whose sector applicability decides

    def plausible(self, threshold: Decimal) -> str | None:
        """None if `threshold` fits the unit, else a message saying what probably went wrong."""
        if self.unit == "ratio" and abs(threshold) > _RATIO_BOUND:
            return (
                f"{self.label} is a ratio stored as a decimal: enter 0.25 for 25%, not 25. "
                f"{threshold} would mean {threshold * 100}%."
            )
        if self.bounds and not self.bounds[0] <= threshold <= self.bounds[1]:
            low, high = self.bounds
            return f"{self.label} runs from {low} to {high}; {threshold} is outside that range."
        return None


def _m(
    key: str,
    label: str,
    group: str,
    unit: Unit,
    periods: tuple[str, ...],
    description: str,
    **extra: object,
) -> TrackedMetric:
    return TrackedMetric(key, label, group, unit, periods, description, **extra)  # type: ignore[arg-type]


_D = Decimal
METRICS: tuple[TrackedMetric, ...] = (
    _m("revenue", "Revenue", "Growth", "usd", ("Q", "TTM", "FY"), "Reported revenue, USD."),
    _m(
        "revenue_yoy",
        "Revenue growth (YoY)",
        "Growth",
        "ratio",
        ("Q", "FY"),
        "Revenue against the same period a year earlier.",
        reader="revenue_yoy",
    ),
    _m("operating_income", "Operating income", "Growth", "usd", ("Q", "TTM", "FY"), "USD."),
    _m("net_income", "Net income", "Growth", "usd", ("Q", "TTM", "FY"), "USD."),
    _m(
        "eps_diluted",
        "EPS (GAAP, diluted)",
        "Growth",
        "usd_per_share",
        ("Q", "TTM", "FY"),
        "USD per share.",
        bounds=(_D(-10000), _D(10000)),
    ),
    _m("operating_cash_flow", "Operating cash flow", "Cash", "usd", ("Q", "TTM", "FY"), "USD."),
    _m("free_cash_flow", "Free cash flow", "Cash", "usd", ("TTM", "FY"), "USD."),
    _m(
        "gross_margin",
        "Gross margin",
        "Margins",
        "ratio",
        ("Q", "TTM", "FY"),
        "Gross profit over revenue.",
    ),
    _m(
        "operating_margin",
        "Operating margin",
        "Margins",
        "ratio",
        ("Q", "TTM", "FY"),
        "Operating income over revenue.",
    ),
    _m("net_margin", "Net margin", "Margins", "ratio", ("FY",), "Net income over revenue."),
    _m(
        "fcf_margin",
        "FCF margin",
        "Margins",
        "ratio",
        ("TTM", "FY"),
        "Free cash flow over revenue.",
    ),
    _m("roic", "ROIC", "Returns", "ratio", ("TTM",), "Return on invested capital."),
    _m("roe", "ROE", "Returns", "ratio", ("FY",), "Return on equity."),
    _m(
        "debt_to_equity",
        "Debt to equity",
        "Balance sheet",
        "ratio",
        ("FY",),
        "Total debt over equity.",
        bounds=(_D(-100), _D(100)),
    ),
    _m(
        "current_ratio",
        "Current ratio",
        "Balance sheet",
        "ratio",
        ("FY",),
        "Current assets over current liabilities.",
        bounds=(_D(0), _D(100)),
    ),
    _m("sbc_pct_revenue", "SBC % of revenue", "Dilution", "ratio", ("FY",), "Decimal."),
    _m("dilution", "Share dilution", "Dilution", "ratio", ("FY",), "Change in diluted shares."),
    _m(
        "piotroski_f",
        "Piotroski F-score",
        "Earnings quality",
        "score",
        ("FY",),
        "0-9 screening score (heuristic).",
        bounds=(_D(0), _D(9)),
    ),
    _m(
        "altman_z",
        "Altman Z-score",
        "Earnings quality",
        "score",
        ("FY",),
        "Distress screening score (heuristic).",
        bounds=(_D(-50), _D(50)),
    ),
    _m(
        "beneish_m",
        "Beneish M-score",
        "Earnings quality",
        "score",
        ("FY",),
        "Earnings-manipulation screening score (heuristic).",
        bounds=(_D(-50), _D(50)),
    ),
    _m("accruals_ratio", "Accruals ratio", "Earnings quality", "ratio", ("TTM", "FY"), "Decimal."),
    _m("fcf_conversion", "FCF conversion", "Earnings quality", "ratio", ("TTM", "FY"), "FCF / NI."),
    _m(
        "pe_ratio",
        "P/E (TTM)",
        "Valuation",
        "multiple",
        ("LATEST",),
        "At the latest close.",
        bounds=(_D(0), _D(1000)),
    ),
    _m(
        "ev_ebitda",
        "EV/EBITDA (TTM)",
        "Valuation",
        "multiple",
        ("LATEST",),
        "At the latest close.",
        bounds=(_D(0), _D(1000)),
    ),
    _m(
        "ps_ratio",
        "P/S (TTM)",
        "Valuation",
        "multiple",
        ("LATEST",),
        "At the latest close.",
        bounds=(_D(0), _D(1000)),
    ),
    _m("fcf_yield", "FCF yield", "Valuation", "ratio", ("LATEST",), "At the latest close."),
    _m(
        "revenue_vs_guidance",
        "Revenue vs guided midpoint",
        "Guidance",
        "ratio",
        ("Q",),
        "Reported revenue over the company's own initial guided midpoint, minus 1 (7i).",
        reader="guidance",
        applies_as="revenue",
    ),
)
BY_KEY = {m.key: m for m in METRICS}
_QUARTER_MARGINS = frozenset({"gross_margin", "operating_margin"})


_DISPLAY_UNIT = {"usd": "USD", "usd_per_share": "USD/shares", "ratio": "ratio", "multiple": "x"}


def shown(value: Decimal, unit: str) -> str:
    """A value in its unit for text: "$96.22 billion", "74.98%", "26.36x", "7"."""
    if unit in _DISPLAY_UNIT:
        return format_metric_value(value, _DISPLAY_UNIT[unit])
    text = f"{value.normalize():f}"
    return f"{text} days" if unit == "days" else text


def applicable(metric: TrackedMetric, company: Company) -> bool:
    """False for a metric the company's sector does not report (a bank's gross margin)."""
    cmap = load_concept_map(ticker=company.ticker, cik=company.cik, sector=company.sector)
    return cmap.applies(metric.applies_as or metric.key)


@dataclass(frozen=True)
class Point:
    period: str  # "Q2-FY2027", "TTM-Q2-FY2027", "FY2026", or a close date for LATEST
    period_end: date | None
    value: Decimal
    source_ids: tuple[str, ...]


def _stored(session: Session, company_id: int, name: str, period_type: str) -> list[Point]:
    rows = metric_repo.get_metric_series(
        session, company_id=company_id, metric_name=name, period_type=period_type
    )
    if period_type == "LATEST":
        rows.sort(key=lambda r: r.period_end or date.min)
    return [
        Point(r.period, r.period_end, r.metric_value, (r.source_id,) if r.source_id else ())
        for r in rows
        if r.metric_value is not None
    ]


def _quarter_margins(session: Session, company_id: int, metric: str) -> list[Point]:
    revenue = _stored(session, company_id, "revenue", "Q")
    labels = {_period(p.period): p for p in revenue}
    rows = guidance_repo.actual_rows(
        session, company_id, labels, {"revenue", "gross_profit", "operating_income"}
    )
    out = []
    for period, point in labels.items():
        actual = actual_for(metric, "ratio", rows.get(period, {}))
        if actual is not None:
            out.append(Point(point.period, point.period_end, actual.value, actual.source_ids))
    return out


def _period(label: str) -> tuple[int, str]:
    """ "Q2-FY2027" -> (2027, "Q2"); "FY2026" -> (2026, "FY")."""
    quarter, _, year = label.rpartition("-FY")
    return (int(year), quarter) if quarter else (int(label[2:]), "FY")


def _yoy(points: Sequence[Point]) -> list[Point]:
    by_period = {_period(p.period): p for p in points}
    out = []
    for (year, part), point in by_period.items():
        prior = by_period.get((year - 1, part))
        if prior is None or prior.value <= 0:
            continue  # growth off a loss or zero is not a number to track
        growth = ((point.value - prior.value) / prior.value).quantize(Decimal("0.000001"))
        out.append(
            Point(point.period, point.period_end, growth, (*point.source_ids, *prior.source_ids))
        )
    return sorted(out, key=lambda p: _period(p.period))


def _guidance(session: Session, company_id: int) -> list[Point]:
    out = []
    for (item, outcome, _doc), _revisions in grouped(
        guidance_repo.items_with_outcomes(session, company_id)
    ):
        if (
            item.metric != "revenue"
            or item.fiscal_period in (None, "FY")
            or outcome is None
            or outcome.delta_vs_mid_pct is None
            or not item.paragraph_id
        ):
            continue
        out.append(
            Point(
                period_label(item).replace(" ", "-"),
                None,
                outcome.delta_vs_mid_pct.quantize(Decimal("0.000001")),
                (item.paragraph_id, *(str(s) for s in outcome.actual_source_ids)),
            )
        )
    return sorted(out, key=lambda p: _period(p.period))


def series(
    session: Session, company: Company, metric: TrackedMetric, period_type: str
) -> list[Point]:
    """The metric's values for one period type, oldest first; the last is the latest."""
    if metric.reader == "guidance":
        return _guidance(session, company.id)
    if metric.reader == "revenue_yoy":
        base = _stored(session, company.id, "revenue", period_type)
        return _yoy(base)
    if metric.key in _QUARTER_MARGINS and period_type == "Q":
        return _quarter_margins(session, company.id, metric.key)
    return _stored(session, company.id, metric.key, period_type)
