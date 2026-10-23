"""Beneish M-score, the 8-variable earnings-manipulation screen (Phase 7d, FR-EQ-003/004).

Source: Beneish, M. D. (1999), "The Detection of Earnings Manipulation", Financial Analysts
Journal 55(5), 24-36. Coefficients and the -1.78 screening threshold as restated by Beneish, Lee &
Nichols (2013, FAJ 69(2)) and Beneish & Vorst (2020); cross-checked against a second source and
quoted in ADR-0042:

    M = -4.84 + 0.920 DSRI + 0.528 GMI + 0.404 AQI + 0.892 SGI + 0.115 DEPI
        - 0.172 SGAI + 4.679 TATA - 0.327 LVGI

A score above -1.78 is "above the screening threshold": a signal to investigate, never a finding.
The model was estimated on non-financial firms (banks excluded), so it is not applicable to them
(DR-EQ-001). Pure and Decimal-only: a missing input or a zero denominator yields
`insufficient_data` naming what is missing; nothing is ever substituted with zero (DR-EQ-002).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.finance import metrics
from app.finance.metrics import Num, Sources, ratio_or_none, year_pair_inputs
from app.schemas.sources import MetricResult

THRESHOLD = Decimal("-1.78")
FORMULA_ID = "beneish_m_score"

_INTERCEPT = Decimal("-4.84")
COEFFICIENTS: dict[str, Decimal] = {
    "dsri": Decimal("0.920"),
    "gmi": Decimal("0.528"),
    "aqi": Decimal("0.404"),
    "sgi": Decimal("0.892"),
    "depi": Decimal("0.115"),
    "sgai": Decimal("-0.172"),
    "tata": Decimal("4.679"),
    "lvgi": Decimal("-0.327"),
}

BELOW = "below_threshold"
ABOVE = "above_threshold"
INSUFFICIENT = "insufficient_data"
NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class BeneishYear:
    """One fiscal year's inputs. None = not reported."""

    revenue: Num = None
    cost_of_revenue: Num = None
    receivables: Num = None
    current_assets: Num = None
    ppe_net: Num = None
    total_assets: Num = None
    depreciation: Num = None
    sga_expense: Num = None
    current_liabilities: Num = None
    long_term_debt: Num = None
    net_income: Num = None
    operating_cash_flow: Num = None


@dataclass(frozen=True)
class BeneishResult:
    """The eight indices, the score and its band, with every input's source ID (FR-EQ-004)."""

    indices: dict[str, Decimal | None]
    score: Decimal | None
    band: str
    metric: MetricResult  # the persisted record: value, inputs (with source IDs), warnings
    missing: list[str] = field(default_factory=list)  # inputs absent, or "<index>: zero base"

    @property
    def source_ids(self) -> list[str]:
        return [i.source_id for i in self.metric.inputs if i.source_id]


def _missing(current: BeneishYear, prior: BeneishYear) -> list[str]:
    return [
        *(name for name, value in vars(current).items() if value is None),
        *(f"prior_{name}" for name, value in vars(prior).items() if value is None),
    ]


def _gross_margin(y: BeneishYear) -> Num:
    if y.revenue is None or y.cost_of_revenue is None:
        return None
    return ratio_or_none(y.revenue - y.cost_of_revenue, y.revenue)


def _soft_assets(y: BeneishYear) -> Num:
    """1 - (current assets + PP&E) / total assets: assets with less certain future benefit."""
    if y.current_assets is None or y.ppe_net is None:
        return None
    hard = ratio_or_none(y.current_assets + y.ppe_net, y.total_assets)
    return None if hard is None else 1 - hard


def _depreciation_rate(y: BeneishYear) -> Num:
    if y.depreciation is None or y.ppe_net is None:
        return None
    return ratio_or_none(y.depreciation, y.depreciation + y.ppe_net)


def _leverage(y: BeneishYear) -> Num:
    if y.current_liabilities is None or y.long_term_debt is None:
        return None
    return ratio_or_none(y.current_liabilities + y.long_term_debt, y.total_assets)


def indices(current: BeneishYear, prior: BeneishYear) -> dict[str, Decimal | None]:
    """The eight Beneish (1999) indices for year t against t-1; None = not computable."""
    c, p = current, prior
    accruals = (
        None
        if c.net_income is None or c.operating_cash_flow is None
        else c.net_income - c.operating_cash_flow
    )
    return {
        "dsri": ratio_or_none(
            ratio_or_none(c.receivables, c.revenue), ratio_or_none(p.receivables, p.revenue)
        ),
        "gmi": ratio_or_none(_gross_margin(p), _gross_margin(c)),
        "aqi": ratio_or_none(_soft_assets(c), _soft_assets(p)),
        "sgi": ratio_or_none(c.revenue, p.revenue),
        "depi": ratio_or_none(_depreciation_rate(p), _depreciation_rate(c)),
        "sgai": ratio_or_none(
            ratio_or_none(c.sga_expense, c.revenue), ratio_or_none(p.sga_expense, p.revenue)
        ),
        # Cash-flow form of total accruals (income - operating cash flow), as in Beneish et al.
        "tata": ratio_or_none(accruals, c.total_assets),
        "lvgi": ratio_or_none(_leverage(c), _leverage(p)),
    }


def band(score: Decimal) -> str:
    return ABOVE if score > THRESHOLD else BELOW


def beneish_m_score(
    current: BeneishYear,
    prior: BeneishYear,
    *,
    applicable: bool = True,
    sources: Sources = None,
) -> BeneishResult:
    """Score year t against t-1. Not applicable for banks; insufficient data names the gap."""
    inputs = year_pair_inputs(current, prior, sources)

    def result(value: Decimal | None, warning: str | None) -> MetricResult:
        return MetricResult(
            value=value,
            unit=metrics.SCORE,
            inputs=inputs,
            formula_id=FORMULA_ID,
            formula_version=metrics.FORMULA_VERSION,
            warnings=[warning] if warning else [],
        )

    if not applicable:
        metric = result(None, metrics.NOT_APPLICABLE_SECTOR)
        return BeneishResult(indices={}, score=None, band=NOT_APPLICABLE, metric=metric)
    values = indices(current, prior)
    absent = _missing(current, prior)
    if absent:
        metric = result(None, metrics.MISSING_INPUT)
        return BeneishResult(values, None, INSUFFICIENT, metric, missing=absent)
    # Every input present but an index undefined means a zero denominator.
    zero = [f"{name}: zero base" for name, value in values.items() if value is None]
    if zero:
        metric = result(None, metrics.NEGATIVE_BASE)
        return BeneishResult(values, None, INSUFFICIENT, metric, missing=zero)
    score = _INTERCEPT + sum(
        (COEFFICIENTS[name] * value for name, value in values.items() if value is not None),
        Decimal(0),
    )
    return BeneishResult(indices=values, score=score, band=band(score), metric=result(score, None))
