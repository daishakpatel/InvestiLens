"""Phase 6a pure-logic units: calendarization, SIC→sector, advice guard, portfolio math (§37).

All offline, no DB. Each test cites the requirement it protects.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.citation.advice import advice_language, contains_advice
from app.comparison.calendar import (
    calendar_year,
    calendarized,
    latest_common_year,
)
from app.finance.sic import sic_to_sector
from app.models import FinancialMetric
from app.portfolio import metrics as pmetrics
from app.portfolio import risk as prisk
from app.portfolio.weights import normalize
from app.schemas.portfolio import Holding

# --- calendarization (DR-021: fiscal periods are separate from calendar dates) ------------------


def test_calendar_year_jan_fye_maps_to_prior_year() -> None:
    # DR-021 / §37.1: NVIDIA FY ending late January belongs to the prior calendar year.
    assert calendar_year(date(2026, 1, 25)) == 2025
    assert calendar_year(date(2025, 1, 26)) == 2024


def test_calendar_year_dec_fye_maps_to_same_year() -> None:
    # §37.1: a December-year company's FY maps to its own calendar year.
    assert calendar_year(date(2025, 12, 27)) == 2025
    assert calendar_year(date(2025, 9, 27)) == 2025  # Apple, late September


def _fy_row(
    fy: int, value: str, period_end: date | None, *, derived: bool = False
) -> FinancialMetric:
    return FinancialMetric(
        company_id=1,
        period=f"FY{fy}",
        fiscal_year=fy,
        period_type="FY",
        metric_name="revenue",
        metric_value=Decimal(value),
        unit="USD",
        is_derived=derived,
        period_end=period_end,
    )


def test_calendarized_uses_fiscal_year_when_period_end_missing() -> None:
    # §37.1: derived rows carry no period_end; calendarization uses fiscal year + FYE month.
    rows = [_fy_row(2026, "100", None, derived=True), _fy_row(2025, "80", None, derived=True)]
    by_year = calendarized(rows, fye_month=1)  # January FYE → FY2026 is CY2025
    assert set(by_year) == {2025, 2024}
    assert by_year[2025].fiscal_year == 2026


def test_calendarized_prefers_period_end_date() -> None:
    rows = [_fy_row(2025, "100", date(2025, 12, 27))]
    assert set(calendarized(rows, fye_month=12)) == {2025}


def test_latest_common_year_is_intersection_max() -> None:
    assert latest_common_year([{2023, 2024, 2025}, {2024, 2025}, {2022, 2024}]) == 2024
    assert latest_common_year([{2023}, {2024}]) is None


# --- SIC → sector (peer grouping + portfolio sector exposure) -----------------------------------


@pytest.mark.parametrize(
    ("sic", "expected"),
    [
        ("3674", "Technology"),  # semiconductors (NVDA/AMD/INTC)
        ("3571", "Technology"),  # electronic computers (AAPL)
        ("6021", "Financials"),  # national commercial banks (JPM)
        ("2834", "Health Care"),  # pharmaceutical preparations
        ("1311", "Energy"),
        (None, None),
        ("", None),
        ("abcd", None),
    ],
)
def test_sic_to_sector(sic: str | None, expected: str | None) -> None:
    assert sic_to_sector(sic) == expected


# --- non-advice guard (LGL-006) -----------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "You should buy NVDA.",
        "We recommend selling the position.",
        "NVDA is a strong buy.",
        "Investors should overweight semiconductors.",
        "This is an attractive entry point.",
        "Our price target implies upside.",
    ],
)
def test_contains_advice_flags_recommendations(text: str) -> None:
    assert contains_advice(text) is True
    assert advice_language(text)


@pytest.mark.parametrize(
    "text",
    [
        "NVIDIA's gross margin exceeded Intel's in calendar year 2025.",
        "AMD's revenue grew faster than Intel's over the period.",
        "The portfolio is concentrated in two sectors.",
    ],
)
def test_contains_advice_allows_neutral_analysis(text: str) -> None:
    assert contains_advice(text) is False


# --- portfolio weights / concentration / sector exposure (§37.2) --------------------------------


def test_normalize_scales_percent_input_to_sum_one() -> None:
    weights = normalize(
        [Holding(ticker="NVDA", weight=Decimal(30)), Holding(ticker="AAPL", weight=Decimal(70))]
    )
    assert sum(w.weight for w in weights) == Decimal(1)
    assert {w.ticker: w.weight for w in weights}["NVDA"] == Decimal("0.3")


def test_normalize_merges_duplicate_tickers() -> None:
    weights = normalize(
        [Holding(ticker="NVDA", weight=Decimal(10)), Holding(ticker="nvda", weight=Decimal(10))]
    )
    assert len(weights) == 1
    assert weights[0].weight == Decimal(1)


def test_holding_schema_rejects_nonpositive_weight() -> None:
    # Validation happens at the schema boundary (Field(gt=0)).
    with pytest.raises(ValueError, match="greater than 0"):
        Holding(ticker="X", weight=Decimal("-1"))


def test_normalize_rejects_nonpositive_defensively() -> None:
    # normalize keeps its own guard for direct callers that bypass the schema (model_construct).
    bad = Holding.model_construct(ticker="X", weight=Decimal("-1"))
    with pytest.raises(ValueError, match="positive"):
        normalize([bad])


def test_concentration_hhi_and_effective_holdings() -> None:
    # §37.2: HHI = Σ wᵢ²; equal thirds → 1/3; effective holdings → 3.
    weights = normalize([Holding(ticker=t, weight=Decimal(1)) for t in ("A", "B", "C")])
    conc = pmetrics.concentration(weights)
    assert conc.hhi == Decimal("0.33333333")
    assert conc.effective_holdings == Decimal("3.00000003")  # 1 / 0.33333333


def test_weighted_metric_renormalizes_over_covered_holdings() -> None:
    # §37.2 / DR-041: a holding with no value (N/A) is excluded and weights renormalized; coverage
    # reflects the missing weight, never a fake 0.
    weights = normalize([Holding(ticker=t, weight=Decimal(1)) for t in ("A", "B", "C")])
    values = {"A": Decimal("0.6"), "B": Decimal("0.3"), "C": None}
    wm = pmetrics.weighted_metric("gross_margin", "ratio", values, weights)
    assert wm.coverage == Decimal("0.66666666")  # two of three thirds
    assert wm.value == Decimal("0.45")  # equal-weighted 0.6 and 0.3
    assert wm.warnings == ["PARTIAL_COVERAGE"]


def test_weighted_metric_no_coverage_is_null() -> None:
    weights = normalize([Holding(ticker="A", weight=Decimal(1))])
    wm = pmetrics.weighted_metric("pe_ratio", "ratio", {"A": None}, weights)
    assert wm.value is None
    assert wm.warnings == ["NO_COVERAGE"]


def test_sector_exposure_sums_by_sector() -> None:
    weights = normalize([Holding(ticker=t, weight=Decimal(1)) for t in ("A", "B", "C")])
    exposure = pmetrics.sector_exposure({"A": "Technology", "B": "Technology", "C": None}, weights)
    top = exposure[0]
    assert top.sector == "Technology"
    assert top.weight == Decimal("0.66666666")
    assert exposure[1].sector == "Unknown"


# --- portfolio risk (§37.2: correlation/volatility deterministic) -------------------------------


def test_daily_returns_and_volatility() -> None:
    series = [
        (date(2025, 1, 1), Decimal(100)),
        (date(2025, 1, 2), Decimal(110)),
        (date(2025, 1, 3), Decimal(99)),
    ]
    returns = prisk.daily_returns(series)
    assert returns[date(2025, 1, 2)] == Decimal("0.1")
    assert prisk.annualized_volatility(returns) is not None


def test_correlation_perfectly_correlated_series_is_one() -> None:
    a = {date(2025, 1, i): Decimal(i) for i in range(1, 6)}
    b = {date(2025, 1, i): Decimal(2 * i) for i in range(1, 6)}  # perfectly linear
    corr = prisk.correlation(a, b)
    assert corr is not None
    assert corr == Decimal(1)


def test_correlation_needs_two_common_points() -> None:
    assert prisk.correlation({date(2025, 1, 1): Decimal(1)}, {date(2025, 1, 2): Decimal(1)}) is None
