"""Quarterly series from raw XBRL facts (Phase 7b, FR-QT-001 … FR-QT-006, ADR-0040).

Pure: facts in, per-quarter values and gap reasons out; persistence is `quarterly_builder`.

A quarter is located by its fiscal year, never by calendar month (FR-QT-005). Fiscal years come
from the company's 10-K full-year spans (plus the year in progress after the latest one), and a
period ending `d` days into a fiscal year is its quarter `classify_duration(d)`: ~91 days is Q1,
~182 Q2, ~273 Q3, a full year Q4. This works for NVIDIA's late-January year end and 53-week years
alike. Three paths, by what the filings report:

- cash-flow flows (`cash_flow_metrics` in the concept map) arrive year-to-date in 10-Qs, so each
  quarter is de-cumulated: Q1 = 3M YTD, Q2 = 6M - 3M, Q3 = 9M - 6M, Q4 = FY - 9M (FR-QT-002);
- income-statement flows arrive as true quarters; Q4 = FY - (Q1 + Q2 + Q3) (DR-022);
- balances are instants read at each quarter end; a per-share or share-count figure is read as
  reported and never derived by subtraction (its Q4 is `not_additive`).

A missing input is never guessed: the quarter is skipped with a reason code (FR-QT-004).
"""

from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from app.finance.concept_map import ConceptMap
from app.finance.derivation import decumulate, derive_q4
from app.finance.periods import PeriodShape, classify_duration, duration_days, fiscal_year_of
from app.finance.selection import FactView, select_fact

QUARTERS_KEPT = 12  # FR-QT-007: the last 12 fiscal quarters per company, never backfilled further

# Gap reason codes (FR-QT-004, stored in `metric_gaps.reason`).
MISSING_YTD = {1: "missing_ytd_1q", 2: "missing_ytd_2q", 3: "missing_ytd_3q", 4: "missing_fy"}
MISSING_QUARTER = {1: "missing_q1", 2: "missing_q2", 3: "missing_q3"}
MISSING_BALANCE = "missing_balance"
NOT_ADDITIVE = "not_additive"  # Q4 EPS / share count: FY - (Q1+Q2+Q3) is meaningless
PERIOD_NOT_REPORTED = "period_not_reported"  # no filing of the company covers that quarter

_QUARTER_OF_SHAPE = {
    PeriodShape.QUARTER: 1,
    PeriodShape.YTD_2Q: 2,
    PeriodShape.YTD_3Q: 3,
    PeriodShape.FULL_YEAR: 4,
}
YTD_NAME = {1: "3M YTD", 2: "6M YTD", 3: "9M YTD", 4: "FY"}


@dataclass(frozen=True, order=True)
class FiscalQuarter:
    fiscal_year: int
    quarter: int  # 1..4

    @property
    def label(self) -> str:
        return f"Q{self.quarter}-FY{self.fiscal_year}"

    def previous(self) -> FiscalQuarter:
        if self.quarter > 1:
            return FiscalQuarter(self.fiscal_year, self.quarter - 1)
        return FiscalQuarter(self.fiscal_year - 1, 4)

    def trailing(self, count: int) -> list[FiscalQuarter]:
        """`count` consecutive fiscal quarters ending with this one, oldest first."""
        quarters = [self]
        while len(quarters) < count:
            quarters.append(quarters[-1].previous())
        return quarters[::-1]


@dataclass(frozen=True)
class FiscalYear:
    fiscal_year: int
    start: date
    end: date | None  # None while the year is in progress (no 10-K yet)


@dataclass(frozen=True)
class QuarterInput:
    """One figure a derived quarter came from, citable by its backend-issued source ID."""

    name: str  # "6M YTD", "FY", "Q2"
    source_id: str | None
    accession: str


@dataclass(frozen=True)
class QuarterValue:
    quarter: FiscalQuarter
    value: Decimal
    unit: str
    source_tag: str
    source_id: str
    period_start: date | None
    period_end: date
    accession: str | None = None  # the filing a directly read value comes from
    formula_id: str | None = None  # set for a computed quarter
    formula: str | None = None  # e.g. "Q3 = 9M YTD - 6M YTD"
    inputs: tuple[QuarterInput, ...] = ()

    @property
    def is_derived(self) -> bool:
        return self.formula is not None


@dataclass
class QuarterlySeries:
    values: dict[FiscalQuarter, QuarterValue] = field(default_factory=dict)
    gaps: dict[FiscalQuarter, str] = field(default_factory=dict)


@dataclass(frozen=True)
class QuarterContext:
    """Everything quarter selection needs for one company, computed once."""

    ticker: str
    concept_map: ConceptMap
    facts_by_tag: Mapping[str, list[FactView]]
    years: Mapping[int, FiscalYear]
    ends: Mapping[FiscalQuarter, date]  # each known fiscal quarter's end date


def fiscal_years(annual_spans: Sequence[tuple[date, date]], fye_month: int) -> list[FiscalYear]:
    """Each reported fiscal year, plus the one in progress after the latest (FR-QT-005)."""
    years = {
        fiscal_year_of(end, fye_month): FiscalYear(fiscal_year_of(end, fye_month), start, end)
        for start, end in sorted(annual_spans, key=lambda span: span[1])
    }
    if annual_spans:
        latest_end = max(end for _, end in annual_spans)
        following = fiscal_year_of(latest_end, fye_month) + 1
        years[following] = FiscalYear(following, latest_end + timedelta(days=1), None)
    return [years[y] for y in sorted(years)]


def quarter_of(year_start: date, period_end: date) -> int | None:
    """The fiscal quarter (1-4) that ends on `period_end`, from its offset into the year."""
    return _QUARTER_OF_SHAPE.get(classify_duration(duration_days(year_start, period_end)))


def build_context(
    ticker: str,
    concept_map: ConceptMap,
    facts: Sequence[FactView],
    annual_spans: Sequence[tuple[date, date]],
    fye_month: int,
) -> QuarterContext:
    tags = {
        t for m in concept_map.flow_metrics + concept_map.stock_metrics for t in concept_map.tags(m)
    }
    facts_by_tag: dict[str, list[FactView]] = {}
    for fact in facts:
        if fact.concept_tag in tags:
            facts_by_tag.setdefault(fact.concept_tag, []).append(fact)
    years = fiscal_years(annual_spans, fye_month)
    return QuarterContext(
        ticker=ticker,
        concept_map=concept_map,
        facts_by_tag=facts_by_tag,
        years={y.fiscal_year: y for y in years},
        ends=_quarter_ends(facts_by_tag, concept_map, years),
    )


def _quarter_ends(
    facts_by_tag: Mapping[str, list[FactView]], concept_map: ConceptMap, years: list[FiscalYear]
) -> dict[FiscalQuarter, date]:
    """Each fiscal quarter's end date, from the reported flow periods ending in it.

    A quarter- or YTD-shaped period ending `d` days into its fiscal year marks the end of quarter
    `classify_duration(d)`, whether it is a 3-month quarter or year-to-date. Q4 ends on the
    fiscal year end. If facts disagree, the most reported end wins, then the earliest, so the
    result never depends on iteration order.
    """
    starts = [y.start for y in years]
    seen: dict[FiscalQuarter, Counter[date]] = {}
    for tag in sorted({t for m in concept_map.flow_metrics for t in concept_map.tags(m)}):
        for fact in facts_by_tag.get(tag, []):
            end = fact.period_end
            shape = classify_duration(duration_days(fact.period_start, end))
            if end is None or fact.period_type != "duration" or shape is PeriodShape.OTHER:
                continue
            index = bisect_right(starts, end) - 1  # the fiscal year the period ends in
            if index < 0:
                continue
            year = years[index]
            quarter = quarter_of(year.start, end)
            if quarter in (1, 2, 3):
                seen.setdefault(FiscalQuarter(year.fiscal_year, quarter), Counter())[end] += 1
    ends = {q: min(c, key=lambda d: (-c[d], d)) for q, c in seen.items()}
    for year in years:
        if year.end is not None:
            ends[FiscalQuarter(year.fiscal_year, 4)] = year.end
    return ends


def kept_quarters(
    ends: Mapping[FiscalQuarter, date], count: int = QUARTERS_KEPT
) -> list[FiscalQuarter]:
    """The last `count` fiscal quarters, ending with the latest one any filing reports."""
    return max(ends).trailing(count) if ends else []


def reports(ctx: QuarterContext, metric: str) -> bool:
    """Whether the company reports the metric at all; one it never reports has no 'gaps'."""
    return any(ctx.facts_by_tag.get(tag) for tag in ctx.concept_map.tags(metric))


def source_id(ticker: str, metric: str, label: str, *, derived: bool) -> str:
    """`xbrl:` for a figure read from a filing, `derived:` for a computed one (FR-QT-007)."""
    return f"{'derived' if derived else 'xbrl'}:{ticker}:{metric}:{label}"


def build_series(
    ctx: QuarterContext, metric: str, quarters: Sequence[FiscalQuarter]
) -> QuarterlySeries:
    """Every requested quarter of one metric: a value, or the reason there is none."""
    series = QuarterlySeries()
    for quarter in quarters:
        year = ctx.years.get(quarter.fiscal_year)
        result = (
            _quarter(ctx, metric, year, quarter)
            if year is not None and quarter in ctx.ends
            else PERIOD_NOT_REPORTED
        )
        if isinstance(result, str):
            series.gaps[quarter] = result
        else:
            series.values[quarter] = result
    return series


def _quarter(
    ctx: QuarterContext, metric: str, year: FiscalYear, quarter: FiscalQuarter
) -> QuarterValue | str:
    cmap = ctx.concept_map
    if cmap.kind(metric) == "stock":
        return _balance(ctx, metric, quarter)
    if cmap.is_cash_flow(metric):
        return _decumulated(ctx, metric, year, quarter)
    if quarter.quarter < 4:
        return _reported_quarter(ctx, metric, quarter)
    if cmap.unit_family(metric) != "currency":
        return NOT_ADDITIVE
    return _fourth_quarter(ctx, metric, year, quarter)


def ytd_fact(
    ctx: QuarterContext, metric: str, year: FiscalYear, quarter: int, *, latest_filed: bool = False
) -> tuple[str, FactView] | None:
    """The year-to-date fact through `quarter` (4 = the full year), by tag priority (DR-QT-001).

    The full year matches any full-year fact ending at the year end, exactly as the annual row
    is selected, so Q1+Q2+Q3+Q4 always equals the stored FY value (DR-QT-004). `latest_filed`
    takes the latest restatement instead (see `select_fact`).
    """
    if quarter == 4:
        end = year.end
        return select_fact(
            ctx.facts_by_tag,
            ctx.concept_map,
            metric,
            lambda f: (
                f.period_type == "duration"
                and f.period_end == end
                and classify_duration(duration_days(f.period_start, f.period_end))
                is PeriodShape.FULL_YEAR
            ),
            latest_filed=latest_filed,
        )
    end = ctx.ends.get(FiscalQuarter(year.fiscal_year, quarter))
    if end is None:
        return None
    return select_fact(
        ctx.facts_by_tag,
        ctx.concept_map,
        metric,
        lambda f: (
            f.period_type == "duration" and f.period_start == year.start and f.period_end == end
        ),
        latest_filed=latest_filed,
    )


def cite(fact: FactView, name: str) -> QuarterInput:
    """A raw fact as a lineage input; `xbrl:<fact_id>` resolves through `GET /sources`."""
    sid = f"xbrl:{fact.fact_id}" if fact.fact_id is not None else None
    return QuarterInput(name=name, source_id=sid, accession=fact.accession_number)


def cite_annual(ctx: QuarterContext, metric: str, fiscal_year: int, fact: FactView) -> QuarterInput:
    """The full year cites the stored annual metric, which has its own ID (ADR-0034)."""
    sid = source_id(ctx.ticker, metric, f"FY{fiscal_year}", derived=False)
    return QuarterInput(name=f"FY{fiscal_year}", source_id=sid, accession=fact.accession_number)


def _reported(
    ctx: QuarterContext, metric: str, quarter: FiscalQuarter, tag: str, fact: FactView
) -> QuarterValue:
    """A figure read straight from a filing; every caller matched it on the quarter's end."""
    return QuarterValue(
        quarter=quarter,
        value=fact.value,
        unit=fact.unit,
        source_tag=tag,
        source_id=source_id(ctx.ticker, metric, quarter.label, derived=False),
        period_start=fact.period_start,
        period_end=ctx.ends[quarter],
        accession=fact.accession_number,
    )


def _start(ctx: QuarterContext, quarter: FiscalQuarter) -> date:
    """A derived quarter (Q2-Q4; Q1 is always read directly) starts after the previous one."""
    return ctx.ends[quarter.previous()] + timedelta(days=1)


def _balance(ctx: QuarterContext, metric: str, quarter: FiscalQuarter) -> QuarterValue | str:
    end = ctx.ends[quarter]
    found = select_fact(
        ctx.facts_by_tag,
        ctx.concept_map,
        metric,
        lambda f: f.period_type == "instant" and f.period_end == end,
    )
    return _reported(ctx, metric, quarter, *found) if found else MISSING_BALANCE


def _quarter_fact(
    ctx: QuarterContext, metric: str, quarter: FiscalQuarter
) -> tuple[str, FactView] | None:
    """A single-quarter (~91-day) fact ending on the quarter's end."""
    end = ctx.ends.get(quarter)
    if end is None:
        return None
    return select_fact(
        ctx.facts_by_tag,
        ctx.concept_map,
        metric,
        lambda f: (
            f.period_type == "duration"
            and f.period_end == end
            and classify_duration(duration_days(f.period_start, f.period_end))
            is PeriodShape.QUARTER
        ),
    )


def _reported_quarter(
    ctx: QuarterContext, metric: str, quarter: FiscalQuarter
) -> QuarterValue | str:
    found = _quarter_fact(ctx, metric, quarter)
    return _reported(ctx, metric, quarter, *found) if found else MISSING_QUARTER[quarter.quarter]


def _decumulated(
    ctx: QuarterContext, metric: str, year: FiscalYear, quarter: FiscalQuarter
) -> QuarterValue | str:
    """Qn = YTD(n) - YTD(n-1); Q1 is its own year-to-date figure (FR-QT-002)."""
    n = quarter.quarter
    current = ytd_fact(ctx, metric, year, n)
    if current is None:
        return MISSING_YTD[n]
    tag, fact = current
    if n == 1:
        return _reported(ctx, metric, quarter, tag, fact)
    prior = ytd_fact(ctx, metric, year, n - 1)
    if prior is None:
        return MISSING_YTD[n - 1]
    first = cite_annual(ctx, metric, year.fiscal_year, fact) if n == 4 else cite(fact, YTD_NAME[n])
    return QuarterValue(
        quarter=quarter,
        value=decumulate([prior[1].value, fact.value])[1],
        unit=fact.unit,
        source_tag=tag,
        source_id=source_id(ctx.ticker, metric, quarter.label, derived=True),
        period_start=_start(ctx, quarter),
        period_end=ctx.ends[quarter],
        formula_id="ytd_decumulation",
        formula=f"Q{n} = {YTD_NAME[n]} - {YTD_NAME[n - 1]}",
        inputs=(first, cite(prior[1], YTD_NAME[n - 1])),
    )


def _fourth_quarter(
    ctx: QuarterContext, metric: str, year: FiscalYear, quarter: FiscalQuarter
) -> QuarterValue | str:
    """Q4 = FY - (Q1 + Q2 + Q3) for an income-statement flow (DR-022)."""
    annual = ytd_fact(ctx, metric, year, 4)
    if annual is None:
        return MISSING_YTD[4]
    tag, fy = annual
    reported: list[FactView] = []
    for n in (1, 2, 3):
        found = _quarter_fact(ctx, metric, FiscalQuarter(year.fiscal_year, n))
        if found is None:
            return MISSING_QUARTER[n]
        reported.append(found[1])
    return QuarterValue(
        quarter=quarter,
        value=derive_q4(fy, *reported).value,
        unit=fy.unit,
        source_tag=tag,
        source_id=source_id(ctx.ticker, metric, quarter.label, derived=True),
        period_start=_start(ctx, quarter),
        period_end=ctx.ends[quarter],
        formula_id="q4_derivation",
        formula="Q4 = FY - (Q1 + Q2 + Q3)",
        inputs=(
            cite_annual(ctx, metric, year.fiscal_year, fy),
            *(cite(f, f"Q{n}") for n, f in enumerate(reported, start=1)),
        ),
    )
