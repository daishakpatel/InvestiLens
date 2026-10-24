"""Valuation multiples as they could have been computed on a given day (Phase 7h, ADR-0046).

Pure functions over raw facts. For a date D only facts *filed on or before D* are used
(DR-PS-003): a 10-K filed after its fiscal year end does not exist yet at that year end, and a
restatement filed later never reaches back. Among the facts known at D, the latest-filed value of
each period is the best knowledge of D.

- TTM flows end at the latest quarter end D's filings report: the twelve-month value itself, or
  the prior fiscal year + this year-to-date - last year's same year-to-date (both YTD figures come
  from the same 10-Q).
- Balances are the instants at that quarter end.
- EBITDA = operating income + D&A; FCF = operating cash flow - capex; enterprise value = market cap
  + total debt + minority interest + preferred - cash - short-term investments.

A multiple whose denominator is zero or negative (a loss, negative EBITDA) or that exceeds
`MAX_MULTIPLE` is `not_meaningful`: shown in words, never as a number, and left out of every
percentile (FR-PS-007). Yields stay meaningful when negative.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.finance import metrics
from app.finance.concept_map import ConceptMap
from app.finance.selection import FactView
from app.schemas.sources import MetricResult

MULTIPLES = (
    "pe_ratio",
    "ps_ratio",
    "ev_revenue",
    "ev_ebitda",
    "ev_fcf",
    "pb_ratio",
    "fcf_yield",
    "earnings_yield",
)
YIELDS = frozenset({"fcf_yield", "earnings_yield"})
MAX_MULTIPLE = Decimal(1000)  # beyond this the denominator is effectively zero

OK = "ok"
NOT_MEANINGFUL = "not_meaningful"
MISSING_INPUT = "missing_input"
NOT_APPLICABLE = "not_applicable"
_STATUS = {
    metrics.NEGATIVE_BASE: NOT_MEANINGFUL,
    metrics.MISSING_INPUT: MISSING_INPUT,
    metrics.NOT_APPLICABLE_SECTOR: NOT_APPLICABLE,
}
_FLOWS = (
    "revenue",
    "net_income",
    "operating_income",
    "depreciation_amortization",
    "operating_cash_flow",
    "capex",
)
_BALANCES = (
    "short_term_debt",
    "long_term_debt",
    "cash_and_equivalents",
    "short_term_investments",
    "shareholders_equity",
    "minority_interest",
    "preferred_stock",
)
_YEAR = (350, 380)  # days in a fiscal year (52/53-week years included)
_SLACK = 10  # days of tolerance when matching periods across filings


@dataclass(frozen=True)
class Figure:
    name: str
    value: Decimal
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class Multiple:
    name: str
    value: Decimal | None  # only when status is ok
    status: str  # ok | not_meaningful | missing_input | not_applicable
    unit: str  # "x" for multiples, "ratio" for yields
    result: MetricResult  # the formula, its inputs and warnings


def known(facts: Sequence[FactView], as_of: date) -> list[FactView]:
    """The facts filed on or before `as_of` (DR-PS-003)."""
    return [f for f in facts if f.filed_date is not None and f.filed_date <= as_of]


def _sources(fact: FactView) -> tuple[str, ...]:
    ids = fact.component_ids or ((fact.fact_id,) if fact.fact_id is not None else ())
    return tuple(f"xbrl:{i}" for i in ids)


def _latest(candidates: list[FactView]) -> FactView:
    """The best knowledge of one period: the latest filing, then the latest row."""
    return max(candidates, key=lambda f: (f.filed_date or date.min, f.fact_id or 0))


def _days(fact: FactView) -> int:
    assert fact.period_start is not None and fact.period_end is not None  # noqa: S101
    return (fact.period_end - fact.period_start).days


def _near(a: date | None, b: date) -> bool:
    return a is not None and abs((a - b).days) <= _SLACK


def latest_quarter_end(facts: Sequence[FactView], cmap: ConceptMap) -> date | None:
    """The latest period end the known filings report revenue or earnings for."""
    tags = {*cmap.tags("revenue"), *cmap.tags("net_income")}
    ends = [f.period_end for f in facts if f.concept_tag in tags and f.period_type == "duration"]
    return max((e for e in ends if e is not None), default=None)


def _durations(facts: Sequence[FactView], tag: str) -> dict[tuple[date, date], FactView]:
    groups: dict[tuple[date, date], list[FactView]] = {}
    for f in facts:
        if f.concept_tag == tag and f.period_type == "duration" and f.period_start and f.period_end:
            groups.setdefault((f.period_start, f.period_end), []).append(f)
    return {period: _latest(group) for period, group in groups.items()}


def _find(periods: dict[tuple[date, date], FactView], end: date, days: int) -> FactView | None:
    for (start, stop), fact in periods.items():
        if _near(stop, end) and abs((stop - start).days - days) <= _SLACK:
            return fact
    return None


def ttm(facts: Sequence[FactView], tags: Sequence[str], quarter_end: date) -> Figure | None:
    """The twelve months to `quarter_end` for the first tag that yields them."""
    for tag in tags:
        periods = _durations(facts, tag)
        ending = [f for (_, stop), f in periods.items() if stop == quarter_end]
        year = next((f for f in ending if _YEAR[0] <= _days(f) <= _YEAR[1]), None)
        if year is not None:
            return Figure(tag, year.value, _sources(year))
        partial = [f for f in ending if _days(f) < _YEAR[0]]
        if not partial:
            continue
        ytd = max(partial, key=_days)
        assert ytd.period_start is not None  # noqa: S101
        prior = _find(periods, quarter_end - timedelta(days=365), _days(ytd))
        previous_year = next(
            (
                f
                for (_, stop), f in periods.items()
                if _near(stop, ytd.period_start - timedelta(days=1))
                and _YEAR[0] <= _days(f) <= _YEAR[1]
            ),
            None,
        )
        if prior is not None and previous_year is not None:
            value = previous_year.value + ytd.value - prior.value
            return Figure(tag, value, (*_sources(previous_year), *_sources(ytd), *_sources(prior)))
    return None


def instant(facts: Sequence[FactView], tags: Sequence[str], quarter_end: date) -> Figure | None:
    """The balance at `quarter_end` for the first tag that reports it."""
    for tag in tags:
        found = [
            f
            for f in facts
            if f.concept_tag == tag and f.period_type == "instant" and f.period_end == quarter_end
        ]
        if found:
            best = _latest(found)
            return Figure(tag, best.value, _sources(best))
    return None


def figures_as_of(
    facts: Sequence[FactView], cmap: ConceptMap, as_of: date
) -> tuple[date | None, dict[str, Figure]]:
    """(latest quarter end known at `as_of`, the TTM flows and balances at it)."""
    seen = known(facts, as_of)
    quarter_end = latest_quarter_end(seen, cmap)
    if quarter_end is None:
        return None, {}
    found: dict[str, Figure] = {}
    for name in _FLOWS:
        figure = ttm(seen, cmap.tags(name), quarter_end)
        if figure is not None:
            found[name] = figure
    for name in _BALANCES:
        figure = instant(seen, cmap.tags(name), quarter_end)
        if figure is not None:
            found[name] = figure
    return quarter_end, found


def _value(figures: Mapping[str, Figure], name: str) -> Decimal | None:
    figure = figures.get(name)
    return figure.value if figure else None


def _combined(figures: Mapping[str, Figure], a: str, b: str, sign: int) -> Decimal | None:
    x, y = _value(figures, a), _value(figures, b)
    return None if x is None or y is None else x + sign * y


def multiples(
    *,
    price: Decimal | None,
    shares: Decimal | None,
    figures: Mapping[str, Figure],
    ev_applies: bool,
    book_applies: bool,
) -> list[Multiple]:
    """Every multiple at one date, with its status. Lineage (each figure's source IDs, the price
    and share count) is recorded by `inputs_record`: a TTM figure rests on several facts."""
    mc = metrics.market_cap(price, shares)
    short, long = _value(figures, "short_term_debt"), _value(figures, "long_term_debt")
    debt = None if short is None and long is None else (short or Decimal(0)) + (long or Decimal(0))
    ev = metrics.enterprise_value(
        mc.value,
        debt,
        _value(figures, "cash_and_equivalents"),
        _value(figures, "short_term_investments"),
        _value(figures, "preferred_stock"),
        _value(figures, "minority_interest"),
        applicable=ev_applies,
    )
    income, revenue = _value(figures, "net_income"), _value(figures, "revenue")
    ebitda = _combined(figures, "operating_income", "depreciation_amortization", 1)
    fcf = _combined(figures, "operating_cash_flow", "capex", -1)
    book = _value(figures, "shareholders_equity")
    results = [
        metrics.pe_from_earnings(mc.value, income),
        metrics.ps_ratio(mc.value, revenue),
        _renamed(metrics.ev_to_revenue(ev.value, revenue, applicable=ev_applies), "ev_revenue"),
        _renamed(metrics.ev_to_ebitda(ev.value, ebitda, applicable=ev_applies), "ev_ebitda"),
        metrics.ev_to_fcf(ev.value, fcf, applicable=ev_applies),
        metrics.pb_ratio(mc.value, book, applicable=book_applies),
        metrics.fcf_yield(fcf, mc.value),
        metrics.earnings_yield(income, mc.value),
    ]
    return [_judge(result) for result in results]


def _renamed(result: MetricResult, name: str) -> MetricResult:
    return result.model_copy(update={"formula_id": name})


def _judge(result: MetricResult) -> Multiple:
    name = result.formula_id
    if result.value is None:
        status = next((_STATUS[w] for w in result.warnings if w in _STATUS), MISSING_INPUT)
        return Multiple(name, None, status, result.unit, result)
    if name not in YIELDS and result.value > MAX_MULTIPLE:
        return Multiple(name, None, NOT_MEANINGFUL, result.unit, result)
    return Multiple(name, result.value, OK, result.unit, result)


def inputs_record(
    quarter_end: date | None, figures: Mapping[str, Figure], extra: Mapping[str, Any]
) -> dict[str, Any]:
    """What a multiple was computed from, for `valuation_history.inputs` (FR-PS-009)."""
    return {
        "quarter_end": quarter_end.isoformat() if quarter_end else None,
        "figures": [
            {"name": n, "value": str(f.value), "tag": f.name, "source_ids": list(f.source_ids)}
            for n, f in sorted(figures.items())
        ],
        **extra,
    }
