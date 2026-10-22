"""Quarterly series and TTM (Phase 7b): pure logic over synthetic facts, fully offline.

The calendar mimics NVIDIA's: fiscal years end the last Sunday of January, so FY2026 runs
2025-01-27 .. 2026-01-25 and its Q1 ends in April 2025 (FR-QT-005).
Refs: FR-QT-001 … FR-QT-009, DR-QT-001 … DR-QT-004, DR-022.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.finance import metrics
from app.finance.concept_map import load_concept_map
from app.finance.periods import PeriodShape, classify_duration
from app.finance.quarterly import (
    MISSING_BALANCE,
    NOT_ADDITIVE,
    PERIOD_NOT_REPORTED,
    FiscalQuarter,
    QuarterContext,
    QuarterValue,
    build_context,
    build_series,
    fiscal_years,
    kept_quarters,
    quarter_of,
    reports,
    ytd_fact,
)
from app.finance.selection import FactView, select_metric
from app.finance.ttm import (
    SHARE_COUNT_CHANGED,
    Cited,
    identity_formula,
    share_count_changed,
    ttm_eps,
    ttm_for,
)

_D = Decimal
_REV = "us-gaap:Revenues"
_OCF = "us-gaap:NetCashProvidedByUsedInOperatingActivities"
_EPS = "us-gaap:EarningsPerShareDiluted"
_CASH = "us-gaap:CashAndCashEquivalentsAtCarryingValue"

FY25 = (date(2024, 1, 29), date(2025, 1, 26))
FY26 = (date(2025, 1, 27), date(2026, 1, 25))
Q_ENDS = {1: date(2025, 4, 27), 2: date(2025, 7, 27), 3: date(2025, 10, 26)}
Q_STARTS = {1: date(2025, 1, 27), 2: date(2025, 4, 28), 3: date(2025, 7, 28)}

_ids = iter(range(1, 10_000))


def flow(
    tag: str,
    start: date,
    end: date,
    value: str,
    *,
    filed: date = date(2026, 3, 1),
    amended: bool = False,
    unit: str = "USD",
) -> FactView:
    return FactView(
        tag, start, end, "duration", _D(value), unit, f"acc-{end}", filed, amended, next(_ids)
    )


def instant(tag: str, end: date, value: str) -> FactView:
    return FactView(tag, None, end, "instant", _D(value), "USD", f"acc-{end}", end, False, None)


def ocf_facts(*, skip_6m: bool = False) -> list[FactView]:
    """YTD-only cash flow, as a 10-Q reports it: 3M 10, 6M 25, 9M 45, FY 70."""
    start = FY26[0]
    facts = [
        flow(_OCF, start, Q_ENDS[1], "10"),
        flow(_OCF, start, Q_ENDS[3], "45"),
        flow(_OCF, *FY26, "70"),
    ]
    if not skip_6m:
        facts.append(flow(_OCF, start, Q_ENDS[2], "25"))
    return facts


def revenue_facts(*, skip_q2: bool = False) -> list[FactView]:
    """True quarters 100/110/120 and FY 500 (so Q4 = 170), plus a prior full year."""
    facts = [flow(_REV, *FY25, "300"), flow(_REV, *FY26, "500")]
    for n, value in ((1, "100"), (2, "110"), (3, "120")):
        if not (skip_q2 and n == 2):
            facts.append(flow(_REV, Q_STARTS[n], Q_ENDS[n], value))
    return facts


def context(facts: list[FactView]) -> QuarterContext:
    cmap = load_concept_map(ticker="NVDA", sector="Technology")
    return build_context("NVDA", cmap, facts, [FY25, FY26], fye_month=1)


FY26_QUARTERS = [FiscalQuarter(2026, n) for n in (1, 2, 3, 4)]


def test_classify_duration_windows() -> None:
    # FR-QT-001: the four shapes 10-Q/10-K periods take, 52/53-week years included.
    assert classify_duration(91) is PeriodShape.QUARTER
    assert classify_duration(98) is PeriodShape.QUARTER  # a 14-week quarter
    assert classify_duration(182) is PeriodShape.YTD_2Q
    assert classify_duration(189) is PeriodShape.YTD_2Q
    assert classify_duration(273) is PeriodShape.YTD_3Q
    assert classify_duration(280) is PeriodShape.YTD_3Q
    assert classify_duration(364) is PeriodShape.FULL_YEAR
    assert classify_duration(371) is PeriodShape.FULL_YEAR
    assert classify_duration(120) is PeriodShape.OTHER
    assert classify_duration(None) is PeriodShape.OTHER


def test_regression_old_q4_path_never_found_ytd_cash_flow() -> None:
    # The pre-fix Q4 derivation looked quarters up with `quarter=True` (an 80-100 day period),
    # but a 10-Q's cash flow is year-to-date (182/273 days): Q2/Q3 were never found, so Q4
    # operating cash flow was silently missing. De-cumulation finds every quarter (DR-QT-004).
    facts = ocf_facts() + revenue_facts()
    cmap = load_concept_map(ticker="NVDA", sector="Technology")
    old_path = [
        select_metric(facts, cmap, "operating_cash_flow", period_end=Q_ENDS[n], quarter=True)
        for n in (1, 2, 3)
    ]
    assert old_path[0] is not None and old_path[1] is None and old_path[2] is None

    series = build_series(context(facts), "operating_cash_flow", FY26_QUARTERS)
    assert [series.values[q].value for q in FY26_QUARTERS] == [_D(10), _D(15), _D(20), _D(25)]
    assert sum(series.values[q].value for q in FY26_QUARTERS) == _D(70)  # == FY, exactly
    assert series.gaps == {}


def test_decumulated_quarters_cite_their_year_to_date_inputs() -> None:
    # FR-QT-002/007, CIT-003: Q1 is read directly; Q2..Q4 are derived with formula + inputs.
    series = build_series(
        context(ocf_facts() + revenue_facts()), "operating_cash_flow", FY26_QUARTERS
    )
    q1, q2, q3, q4 = (series.values[q] for q in FY26_QUARTERS)
    assert not q1.is_derived and q1.source_id == "xbrl:NVDA:operating_cash_flow:Q1-FY2026"
    assert q3.source_id == "derived:NVDA:operating_cash_flow:Q3-FY2026"
    assert q3.formula == "Q3 = 9M YTD - 6M YTD" and q3.formula_id == "ytd_decumulation"
    assert [i.name for i in q3.inputs] == ["9M YTD", "6M YTD"]
    assert all(i.source_id and i.source_id.startswith("xbrl:") for i in q3.inputs)
    assert q4.formula == "Q4 = FY - 9M YTD"
    assert q4.inputs[0].source_id == "xbrl:NVDA:operating_cash_flow:FY2026"  # the stored annual
    assert q2.period_start == date(2025, 4, 28) and q2.period_end == Q_ENDS[2]


def test_missing_ytd_input_is_a_gap_never_a_guess() -> None:
    # FR-QT-004: without the 6M YTD figure, Q2 (6M - 3M) and Q3 (9M - 6M) cannot exist.
    series = build_series(
        context(ocf_facts(skip_6m=True) + revenue_facts()), "operating_cash_flow", FY26_QUARTERS
    )
    assert series.gaps == {
        FiscalQuarter(2026, 2): "missing_ytd_2q",
        FiscalQuarter(2026, 3): "missing_ytd_2q",
    }
    assert set(series.values) == {FiscalQuarter(2026, 1), FiscalQuarter(2026, 4)}
    assert series.values[FiscalQuarter(2026, 4)].value == _D(25)  # FY - 9M needs no 6M


def test_missing_full_year_or_first_quarter_is_named() -> None:
    start = FY26[0]
    facts = [flow(_OCF, start, Q_ENDS[2], "25"), *revenue_facts()]  # no 3M, no FY
    series = build_series(context(facts), "operating_cash_flow", FY26_QUARTERS)
    assert series.gaps[FiscalQuarter(2026, 1)] == "missing_ytd_1q"
    assert series.gaps[FiscalQuarter(2026, 2)] == "missing_ytd_1q"  # 6M - (missing) 3M
    assert series.gaps[FiscalQuarter(2026, 4)] == "missing_fy"


def test_january_fiscal_year_end_labels_quarters_by_fiscal_year() -> None:
    # FR-QT-005: a quarter ending in April 2025 is Q1 of FY2026, not a calendar Q2 of 2025.
    series = build_series(context(revenue_facts()), "revenue", FY26_QUARTERS)
    q1, q4 = series.values[FiscalQuarter(2026, 1)], series.values[FiscalQuarter(2026, 4)]
    assert (q1.quarter.label, q1.period_end) == ("Q1-FY2026", date(2025, 4, 27))
    assert (q4.quarter.label, q4.period_end) == ("Q4-FY2026", date(2026, 1, 25))
    assert quarter_of(FY26[0], date(2025, 4, 27)) == 1
    assert quarter_of(FY26[0], date(2026, 1, 25)) == 4
    assert quarter_of(FY26[0], date(2025, 6, 1)) is None  # not a quarter end


def test_income_q4_is_fy_minus_three_quarters() -> None:
    # DR-022, FR-QT-006: income-statement flows arrive as true quarters; Q4 = FY - (Q1+Q2+Q3).
    series = build_series(context(revenue_facts()), "revenue", FY26_QUARTERS)
    q4 = series.values[FiscalQuarter(2026, 4)]
    assert q4.value == _D(170) and q4.formula == "Q4 = FY - (Q1 + Q2 + Q3)"
    assert [i.name for i in q4.inputs] == ["FY2026", "Q1", "Q2", "Q3"]
    assert sum(series.values[q].value for q in FY26_QUARTERS) == _D(500)

    missing = build_series(
        context(revenue_facts(skip_q2=True) + ocf_facts()), "revenue", FY26_QUARTERS
    )  # the 10-Q exists (its cash flow ends in Q2); only its revenue quarter is missing
    assert missing.gaps == {
        FiscalQuarter(2026, 2): "missing_q2",
        FiscalQuarter(2026, 4): "missing_q2",
    }


def test_income_q4_without_full_year_is_missing_fy() -> None:
    facts = [f for f in revenue_facts() if f.period_end != FY26[1]] + ocf_facts()
    series = build_series(context(facts), "revenue", FY26_QUARTERS)
    assert series.gaps[FiscalQuarter(2026, 4)] == "missing_fy"


def test_per_share_q4_balances_and_unreported_periods() -> None:
    eps = [
        flow(_EPS, Q_STARTS[n], Q_ENDS[n], v, unit="USD/shares")
        for n, v in ((1, "1"), (2, "1"), (3, "1"))
    ]
    facts = revenue_facts() + ocf_facts() + eps + [instant(_CASH, Q_ENDS[1], "9")]
    ctx = context(facts)
    quarters = [FiscalQuarter(2024, 4), *FY26_QUARTERS]
    series = build_series(ctx, "eps_diluted", quarters)
    assert series.gaps[FiscalQuarter(2026, 4)] == NOT_ADDITIVE  # FY - sum(EPS) is meaningless
    assert series.gaps[FiscalQuarter(2024, 4)] == PERIOD_NOT_REPORTED  # no filing covers FY2024
    cash = build_series(ctx, "cash_and_equivalents", FY26_QUARTERS)
    assert (
        cash.values[FiscalQuarter(2026, 1)].source_id == "xbrl:NVDA:cash_and_equivalents:Q1-FY2026"
    )
    assert cash.gaps[FiscalQuarter(2026, 2)] == MISSING_BALANCE
    assert reports(ctx, "cash_and_equivalents") and not reports(ctx, "inventory")


def test_restated_quarter_keeps_the_as_reported_value() -> None:
    # DR-QT-001: same (concept, period, shape) twice -> earliest filed wins, unless amended.
    original = flow(_REV, Q_STARTS[1], Q_ENDS[1], "100", filed=date(2025, 5, 28))
    comparative = flow(_REV, Q_STARTS[1], Q_ENDS[1], "101", filed=date(2026, 5, 28))
    base = revenue_facts()[:2] + ocf_facts()
    series = build_series(context([*base, comparative, original]), "revenue", FY26_QUARTERS[:1])
    assert series.values[FiscalQuarter(2026, 1)].value == _D(100)

    amendment = flow(_REV, Q_STARTS[1], Q_ENDS[1], "99", filed=date(2025, 6, 30), amended=True)
    series = build_series(context([*base, original, amendment]), "revenue", FY26_QUARTERS[:1])
    assert series.values[FiscalQuarter(2026, 1)].value == _D(99)


def test_quarter_end_disagreement_resolves_deterministically() -> None:
    start = FY26[0]
    facts = [
        *revenue_facts()[:2],
        flow(_OCF, start, date(2025, 4, 26), "1"),  # one fact says the 26th ...
        flow(_REV, start, date(2025, 4, 27), "100"),  # ... two say the 27th
        flow(_EPS, start, date(2025, 4, 27), "1", unit="USD/shares"),
    ]
    assert context(facts).ends[FiscalQuarter(2026, 1)] == date(2025, 4, 27)  # most reported
    tie = [
        *revenue_facts()[:2],
        flow(_OCF, start, date(2025, 4, 28), "1"),
        flow(_REV, start, date(2025, 4, 27), "1"),
    ]
    assert context(tie).ends[FiscalQuarter(2026, 1)] == date(2025, 4, 27)  # tie -> earliest


def test_fiscal_years_include_the_year_in_progress() -> None:
    years = fiscal_years([FY26, FY25], fye_month=1)
    assert [(y.fiscal_year, y.end) for y in years] == [
        (2025, FY25[1]),
        (2026, FY26[1]),
        (2027, None),
    ]
    assert years[-1].start == date(2026, 1, 26)
    assert fiscal_years([], fye_month=12) == []
    assert kept_quarters({}) == []
    assert kept_quarters({FiscalQuarter(2026, 2): date(2025, 7, 27)}, count=3) == [
        FiscalQuarter(2025, 4),
        FiscalQuarter(2026, 1),
        FiscalQuarter(2026, 2),
    ]


# --- TTM -----------------------------------------------------------------------------


def _quarterly(
    values: dict[FiscalQuarter, str], unit: str = "USD"
) -> dict[FiscalQuarter, QuarterValue]:
    return {
        q: QuarterValue(q, _D(v), unit, "tag", f"xbrl:T:m:{q.label}", None, date(2026, 1, 1))
        for q, v in values.items()
    }


WINDOW = [
    FiscalQuarter(2025, 4),
    FiscalQuarter(2026, 1),
    FiscalQuarter(2026, 2),
    FiscalQuarter(2026, 3),
]


def test_ttm_flow_needs_all_four_quarters() -> None:
    # FR-QT-008, DR-QT-002: four consecutive quarters summed; three are never annualized.
    full = _quarterly(dict(zip(WINDOW, ("1", "2", "3", "4"), strict=True)))
    result = ttm_for(full, WINDOW[-1], kind="flow")
    assert result.value == _D(10) and result.formula_id == "ttm_sum"
    assert [i.name for i in result.inputs] == [q.label for q in WINDOW]
    assert result.inputs[0].source_id == "xbrl:T:m:Q4-FY2025"

    three = _quarterly(dict(zip(WINDOW[1:], ("2", "3", "4"), strict=True)))
    missing = ttm_for(three, WINDOW[-1], kind="flow")
    assert missing.value is None and missing.warnings == [metrics.MISSING_INPUT]


def test_ttm_of_a_balance_is_the_latest_balance() -> None:
    # FR-QT-008: cash, debt, equity: TTM means the balance at the window's end, not a sum.
    balances = _quarterly({WINDOW[-2]: "50", WINDOW[-1]: "60"})
    result = ttm_for(balances, WINDOW[-1], kind="stock")
    assert result.value == _D(60) and result.formula_id == "latest_balance"
    assert result.inputs[0].source_id == "xbrl:T:m:Q3-FY2026"
    absent = ttm_for(balances, FiscalQuarter(2026, 4), kind="stock")
    assert absent.value is None and absent.warnings == [metrics.MISSING_INPUT]


def test_ttm_margin_is_ttm_numerator_over_ttm_denominator() -> None:
    # DR-QT-003: with unequal quarters, averaging quarterly margins is visibly wrong.
    revenue = _quarterly(dict(zip(WINDOW, ("1000", "100", "100", "100"), strict=True)))
    gross = _quarterly(dict(zip(WINDOW, ("900", "10", "10", "10"), strict=True)))
    ttm_rev = ttm_for(revenue, WINDOW[-1], kind="flow").value
    ttm_gross = ttm_for(gross, WINDOW[-1], kind="flow").value
    margin = metrics.gross_margin(ttm_gross, ttm_rev).value
    averaged = sum((gross[q].value / revenue[q].value for q in WINDOW), _D(0)) / 4
    assert margin == _D(930) / _D(1300)  # ~71.5%
    assert averaged == _D("0.3")  # 30%: what averaging would have said
    assert margin is not None and abs(margin - averaged) > _D("0.4")


def test_ttm_eps_sums_quarters_when_all_four_exist() -> None:
    quarterly = _quarterly(dict(zip(WINDOW, ("1", "1", "1", "2"), strict=True)), "USD/shares")
    result = ttm_eps(quarterly, WINDOW[-1], [], unit="USD/shares")
    assert result.value == _D(5) and result.unit == "USD/shares" and result.formula_id == "ttm_sum"


def test_ttm_eps_uses_the_year_to_date_identity() -> None:
    # FR-QT-008: FY_prior - YTD_prior + YTD_current when quarterly EPS are incomplete.
    identity = [
        (1, Cited("FY2025", _D("13.00"), "xbrl:T:eps_diluted:FY2025")),
        (-1, Cited("9M YTD FY2025", _D("3.00"), "xbrl:1")),
        (1, Cited("9M YTD FY2026", _D("3.30"), "xbrl:2")),
    ]
    result = ttm_eps({}, WINDOW[-1], identity, unit="USD/shares")
    assert result.value == _D("13.30") and result.formula_id == "ttm_eps_identity"
    assert [i.source_id for i in result.inputs] == ["xbrl:T:eps_diluted:FY2025", "xbrl:1", "xbrl:2"]
    assert identity_formula(identity) == "TTM = FY2025 - 9M YTD FY2025 + 9M YTD FY2026"

    gap = ttm_eps({}, WINDOW[-1], [identity[0], (-1, None), identity[2]], unit="USD/shares")
    assert gap.value is None and gap.warnings == [metrics.MISSING_INPUT]
    assert gap.inputs[1].name == "missing"
    assert ttm_eps({}, WINDOW[-1], [], unit="USD/shares").value is None


def test_share_count_change_over_five_percent_is_flagged() -> None:
    # FR-QT-009: first and last quarter in the window that report diluted shares.
    assert share_count_changed([None, _D(100), _D(103), _D(110)]) is True  # +10%
    assert share_count_changed([_D(100), None, _D(104), _D(105)]) is False  # exactly 5%
    assert share_count_changed([None, None, None, _D(100)]) is False  # nothing to compare
    assert SHARE_COUNT_CHANGED == "share_count_changed"


def test_new_formulas() -> None:
    assert metrics.effective_tax_rate(_D(21), _D(100)).value == _D("0.21")
    assert metrics.effective_tax_rate(_D(5), _D(-10)).warnings == [metrics.NEGATIVE_BASE]
    banks = metrics.roic(_D(1), _D(0), _D(1), _D(1), _D(0), applicable=False)
    assert banks.value is None and banks.warnings == [metrics.NOT_APPLICABLE_SECTOR]
    labelled = metrics.ttm_sum([_D(1)] * 4, labels=["a", "b", "c", "d"], unit="USD/shares")
    assert [i.name for i in labelled.inputs] == [
        "a",
        "b",
        "c",
        "d",
    ] and labelled.unit == "USD/shares"


def test_latest_filed_selection_takes_the_split_restated_figure() -> None:
    # ADR-0040: a stock split restates prior per-share figures in later filings. The TTM EPS
    # identity takes each term's latest restatement so all terms share one share basis; the
    # stored quarters keep the as-reported figure (DR-QT-001).
    as_filed = flow(_EPS, *FY25, "11.93", filed=date(2025, 2, 21), unit="USD/shares")
    restated = flow(_EPS, *FY25, "1.19", filed=date(2026, 2, 25), unit="USD/shares")
    ctx = context([*revenue_facts(), *ocf_facts(), restated, as_filed])
    year = ctx.years[2025]
    reported = ytd_fact(ctx, "eps_diluted", year, 4)
    latest = ytd_fact(ctx, "eps_diluted", year, 4, latest_filed=True)
    assert reported is not None and reported[1].value == _D("11.93")
    assert latest is not None and latest[1].value == _D("1.19")


def test_quarter_ends_ignore_odd_periods_and_years_before_the_first() -> None:
    # FR-QT-001/005: a 120-day period is no quarter, and a quarter ending before the first known
    # fiscal year belongs to no year we can label, so neither marks a quarter end.
    odd = flow(_OCF, FY26[0], date(2025, 5, 26), "1")  # 120 days
    early = flow(_REV, date(2023, 10, 1), date(2023, 12, 30), "1")  # before FY2025 starts
    ends = context([*revenue_facts(), odd, early]).ends
    assert date(2025, 5, 26) not in ends.values() and date(2023, 12, 30) not in ends.values()
