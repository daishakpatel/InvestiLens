"""Point-in-time valuation, composite tags and valuation bands, offline (Phase 7h).

Requirement IDs: FR-PS-005/006/007/009/010/011, DR-PS-001/002/003.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app.citation.advice import contains_advice
from app.comparison import bands
from app.finance import metrics
from app.finance import point_in_time as pit
from app.finance.concept_map import load_concept_map
from app.finance.facts import with_composites
from app.finance.selection import FactView, select_metric
from app.finance.valuation_builder import ShareCount, count_as_of
from app.models import ValuationHistory

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "composites"
_CMAP = load_concept_map(ticker="TEST")


def _fact(
    tag: str,
    start: date | None,
    end: date,
    value: int,
    filed: date,
    *,
    fact_id: int = 1,
    kind: str = "duration",
) -> FactView:
    return FactView(
        concept_tag=tag,
        period_start=start,
        period_end=end,
        period_type=kind,
        value=Decimal(value),
        unit="USD",
        accession_number=f"acc-{filed.isoformat()}",
        filed_date=filed,
        fact_id=fact_id,
    )


REV = "us-gaap:Revenues"
REV_ALT = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"


def _quarterly_facts() -> list[FactView]:
    """FY2024 (Jan-Dec) revenue 400, then 9 months of 2025 = 330 (Q3 10-Q, filed 2025-11-05),
    with the prior 9 months = 300 as its comparative: TTM to 2025-09-30 = 400 + 330 - 300."""
    return [
        _fact(REV_ALT, date(2024, 1, 1), date(2024, 12, 31), 400, date(2025, 2, 10), fact_id=1),
        _fact(REV, date(2024, 1, 1), date(2024, 9, 30), 300, date(2024, 11, 5), fact_id=2),
        _fact(REV, date(2025, 1, 1), date(2025, 9, 30), 330, date(2025, 11, 5), fact_id=3),
        _fact(REV, date(2025, 7, 1), date(2025, 9, 30), 120, date(2025, 11, 5), fact_id=4),
    ]


# --- DR-PS-003 point in time ------------------------------------------------------------------
def test_ttm_from_ytd_merges_tags_per_period() -> None:
    facts = _quarterly_facts()
    figure = pit.ttm(facts, [REV, REV_ALT], date(2025, 9, 30))
    assert figure is not None and figure.value == Decimal(430)
    assert figure.source_ids == ("xbrl:1", "xbrl:3", "xbrl:2")  # prior FY, this YTD, prior YTD


def test_full_year_ttm_and_gaps() -> None:
    annual = [_fact(REV, date(2024, 1, 1), date(2024, 12, 31), 400, date(2025, 2, 10))]
    assert pit.ttm(annual, [REV], date(2024, 12, 31)) == pit.Figure(REV, Decimal(400), ("xbrl:1",))
    assert pit.ttm(annual, [REV], date(2025, 9, 30)) is None  # nothing ends there
    no_prior = [f for f in _quarterly_facts() if f.fact_id != 2]
    assert pit.ttm(no_prior, [REV, REV_ALT], date(2025, 9, 30)) is None  # never a partial year


def test_a_restatement_filed_after_d_does_not_change_ds_multiple() -> None:
    """DR-PS-003: the 9-month revenue was restated to 360 in a filing made after D. On D the
    multiple must still use 330; a day after the restatement, 360."""
    restated = _fact(REV, date(2025, 1, 1), date(2025, 9, 30), 360, date(2026, 3, 1), fact_id=9)
    facts = [*_quarterly_facts(), restated]
    on_d = date(2025, 12, 31)
    assert pit.figures_as_of(facts, _CMAP, on_d)[1]["revenue"].value == Decimal(430)
    after = date(2026, 3, 2)
    assert pit.figures_as_of(facts, _CMAP, after)[1]["revenue"].value == Decimal(460)
    # Before any filing there is nothing to value.
    assert pit.figures_as_of(facts, _CMAP, date(2024, 1, 1)) == (None, {})


def test_balances_are_the_known_instant_at_the_quarter_end() -> None:
    cash = "us-gaap:CashAndCashEquivalentsAtCarryingValue"
    facts = [
        _fact(cash, None, date(2025, 9, 30), 50, date(2025, 11, 5), fact_id=5, kind="instant"),
        _fact(cash, None, date(2025, 9, 30), 55, date(2026, 2, 1), fact_id=6, kind="instant"),
    ]
    assert pit.instant(pit.known(facts, date(2025, 12, 1)), [cash], date(2025, 9, 30)) == (
        pit.Figure(cash, Decimal(50), ("xbrl:5",))
    )
    assert pit.instant(facts, [cash], date(2025, 9, 30)).value == Decimal(55)  # type: ignore[union-attr]
    assert pit.instant(facts, [cash], date(2025, 6, 30)) is None


def test_share_counts_are_point_in_time() -> None:
    counts = [
        ShareCount(date(2025, 10, 20), Decimal(100), "xbrl:1", date(2025, 11, 5)),
        ShareCount(date(2026, 1, 20), Decimal(110), "xbrl:2", date(2026, 2, 20)),
    ]
    assert count_as_of(counts, date(2025, 12, 31)) == counts[0]
    assert count_as_of(counts, date(2026, 2, 1)) == counts[0]  # dated, but not yet filed
    assert count_as_of(counts, date(2025, 1, 1)) is None


# --- FR-PS-005/007 multiples ------------------------------------------------------------------
def _figures(**values: int) -> dict[str, pit.Figure]:
    return {name: pit.Figure(name, Decimal(v), (f"xbrl:{name}",)) for name, v in values.items()}


_FULL = _figures(
    revenue=1000,
    net_income=100,
    operating_income=150,
    depreciation_amortization=50,
    operating_cash_flow=180,
    capex=30,
    short_term_debt=20,
    long_term_debt=80,
    cash_and_equivalents=60,
    short_term_investments=40,
    shareholders_equity=500,
    minority_interest=10,
    preferred_stock=5,
)


def _by_name(results: list[pit.Multiple]) -> dict[str, pit.Multiple]:
    return {m.name: m for m in results}


def test_every_multiple_and_the_ev_formula() -> None:
    out = _by_name(
        pit.multiples(
            price=Decimal(20),
            shares=Decimal(100),
            figures=_FULL,
            ev_applies=True,
            book_applies=True,
        )
    )
    # market cap 2,000; EV = 2,000 + 100 debt + 5 preferred + 10 minority - 60 cash - 40 STI = 2,015
    assert {n: m.value for n, m in out.items()} == {
        "pe_ratio": Decimal(20),
        "ps_ratio": Decimal(2),
        "ev_revenue": Decimal("2.015"),
        "ev_ebitda": Decimal("10.075"),
        "ev_fcf": Decimal("13.43333333333333333333333333"),
        "pb_ratio": Decimal(4),
        "fcf_yield": Decimal("0.075"),
        "earnings_yield": Decimal("0.05"),
    }
    assert all(m.status == pit.OK for m in out.values())
    assert out["fcf_yield"].unit == "ratio" and out["pe_ratio"].unit == "x"


def test_losses_are_not_meaningful_and_yields_stay_negative() -> None:
    """FR-PS-007: a loss is never a negative P/E, and a near-zero denominator is not a value."""
    loss = _FULL | _figures(net_income=-50, operating_income=-60, depreciation_amortization=10)
    out = _by_name(
        pit.multiples(
            price=Decimal(20), shares=Decimal(100), figures=loss, ev_applies=True, book_applies=True
        )
    )
    assert out["pe_ratio"].status == pit.NOT_MEANINGFUL and out["pe_ratio"].value is None
    assert out["ev_ebitda"].status == pit.NOT_MEANINGFUL
    assert out["earnings_yield"].value == Decimal("-0.025")  # a yield can be negative
    tiny = _FULL | _figures(net_income=1)
    pe = _by_name(
        pit.multiples(
            price=Decimal(20), shares=Decimal(100), figures=tiny, ev_applies=True, book_applies=True
        )
    )["pe_ratio"]
    assert pe.status == pit.NOT_MEANINGFUL  # 2,000x: beyond MAX_MULTIPLE


def test_banks_and_missing_inputs() -> None:
    out = _by_name(
        pit.multiples(
            price=Decimal(20),
            shares=Decimal(100),
            figures=_figures(revenue=1000, net_income=100),
            ev_applies=False,
            book_applies=False,
        )
    )
    assert (
        out["ev_ebitda"].status == pit.NOT_APPLICABLE
        and out["pb_ratio"].status == pit.NOT_APPLICABLE
    )
    assert out["fcf_yield"].status == pit.MISSING_INPUT
    none = _by_name(
        pit.multiples(price=None, shares=None, figures={}, ev_applies=True, book_applies=True)
    )
    assert {m.status for m in none.values()} == {pit.MISSING_INPUT}


def test_derived_values_need_both_parts_except_debt() -> None:
    derived = pit.derived_values(_figures(long_term_debt=80, operating_income=150))
    assert derived["total_debt"] == (Decimal(80), ("xbrl:long_term_debt",))
    assert "ebitda" not in derived and "free_cash_flow" not in derived
    record = pit.inputs_record(date(2025, 9, 30), _figures(revenue=5), {"price": None})
    assert record == {
        "quarter_end": "2025-09-30",
        "figures": [
            {"name": "revenue", "value": "5", "tag": "revenue", "source_ids": ["xbrl:revenue"]}
        ],
        "price": None,
    }
    assert pit.inputs_record(None, {}, {})["quarter_end"] is None


def test_new_formulas() -> None:
    assert metrics.pe_from_earnings(Decimal(100), Decimal(0)).warnings == [metrics.NEGATIVE_BASE]
    assert metrics.ev_to_fcf(Decimal(1), Decimal(1), applicable=False).warnings == [
        metrics.NOT_APPLICABLE_SECTOR
    ]
    assert metrics.pb_ratio(Decimal(1), Decimal(1), applicable=False).warnings == [
        metrics.NOT_APPLICABLE_SECTOR
    ]
    assert metrics.earnings_yield(Decimal(-5), Decimal(100)).value == Decimal("-0.05")


# --- FR-PS-006 composite D&A golden values ------------------------------------------------------
def _recorded(ticker: str) -> list[FactView]:
    raw = json.loads((_FIXTURES / "amd_intc_fy2025_da_facts.json").read_text())["facts"][ticker]
    return [
        FactView(
            concept_tag=f["concept_tag"],
            period_start=date.fromisoformat(f["period_start"]),
            period_end=date.fromisoformat(f["period_end"]),
            period_type="duration",
            value=Decimal(f["value"]),
            unit=f["unit"],
            accession_number=f["accession_number"],
            filed_date=date.fromisoformat(f["filed_date"]),
            fact_id=i + 1,
        )
        for i, f in enumerate(raw)
    ]


@pytest.mark.parametrize(
    ("ticker", "expected"),
    [
        # AMD FY2025: OtherDepreciationAndAmortization 750 + AmortizationOfIntangibleAssets 2,300;
        # the cash-flow statement shows 750 + 2,254 (AMD's own tag): $46M is counted twice.
        ("AMD", Decimal(3_050_000_000)),
        # Intel FY2025: Depreciation 10,757 + amortization of intangibles 949 (its statement).
        ("INTC", Decimal(11_706_000_000)),
    ],
)
def test_composite_depreciation_and_amortization(ticker: str, expected: Decimal) -> None:
    cmap = load_concept_map(ticker=ticker)
    facts = with_composites(_recorded(ticker), cmap.composites)
    selection = select_metric(
        facts, cmap, "depreciation_amortization", period_end=date(2025, 12, 27)
    )
    assert selection is not None and selection.value == expected
    assert selection.source_tag == "composite:depreciation_amortization"
    composite = next(f for f in facts if f.concept_tag.startswith("composite:"))
    assert len(composite.component_ids) == 2


def test_a_composite_needs_every_component() -> None:
    cmap = load_concept_map(ticker="INTC")
    partial = [f for f in _recorded("INTC") if f.concept_tag == "us-gaap:Depreciation"]
    assert not any(
        f.concept_tag.startswith("composite:") for f in with_composites(partial, cmap.composites)
    )
    assert load_concept_map(ticker="NVDA").composites == {}


# --- FR-PS-009/010/011 bands --------------------------------------------------------------------
def test_own_band_thresholds() -> None:
    short = bands.own_band(Decimal(10), [Decimal(8), Decimal(9)])
    assert (
        short.percentile is None
        and short.min is None
        and "Insufficient history" in (short.reason or "")
    )
    four = bands.own_band(Decimal(10), [Decimal(8), Decimal(9), Decimal(12)])
    assert four.n == 4 and four.percentile is None and "needs 5" in (four.reason or "")
    assert (four.min, four.median, four.max) == (Decimal(8), Decimal("9.5"), Decimal(12))
    full = bands.own_band(
        Decimal(30), [Decimal(10), Decimal(20), Decimal(25), Decimal(28), Decimal(29)]
    )
    assert full.n == 6 and full.percentile == Decimal(1)
    assert full.label == "in the top quartile of its 5-year range"
    no_today = bands.own_band(None, [Decimal(1), Decimal(2), Decimal(3)])
    assert no_today.percentile is None and "No value today" in (no_today.reason or "")


def _row(value: str | None, status: str = pit.OK) -> ValuationHistory:
    return ValuationHistory(value=Decimal(value) if value else None, status=status)


def test_peer_band_excludes_and_explains() -> None:
    peers: list[tuple[str, Any]] = [
        ("AAA", _row("10")),
        ("BBB", _row("20")),
        ("CCC", _row("30")),
        ("DDD", _row(None, pit.NOT_MEANINGFUL)),
        ("EEE", None),
        ("FFF", _row(None, pit.MISSING_INPUT)),
    ]
    band = bands.peer_band(Decimal("23.6"), peers, insufficient_set=False)
    assert band.n == 3 and band.median == Decimal(20)
    assert band.premium_to_peer_median == Decimal("0.18") and band.label == "18% above peer median"
    assert [e.ticker for e in band.excluded] == ["DDD", "EEE", "FFF"]
    assert band.excluded[0].reason.startswith("Not meaningful")
    assert band.excluded[2].reason.startswith(
        "Not available: a price, share count or four quarters"
    )
    assert bands.peer_band(Decimal(1), peers, insufficient_set=True).reason.startswith(  # type: ignore[union-attr]
        "Insufficient peers"
    )
    few = bands.peer_band(Decimal(1), peers[:2], insufficient_set=False)
    assert few.median is None and few.percentile is None and "need 3 peers" in (few.reason or "")
    no_today = bands.peer_band(None, peers, insufficient_set=False)
    assert no_today.median == Decimal(20) and no_today.premium_to_peer_median is None


@pytest.mark.parametrize(
    ("premium", "label"),
    [
        (Decimal("-0.25"), "25% below peer median"),
        (Decimal("0.001"), "in line with the peer median"),
    ],
)
def test_premium_labels(premium: Decimal, label: str) -> None:
    assert bands.premium_label(premium) == label


def test_no_label_or_reason_judges_value() -> None:
    """FR-PS-011: every band template passes the advice guard; the guard catches value calls."""
    texts = [
        *(bands.position_label(Decimal(p)) for p in ("0.1", "0.5", "0.9")),
        *(bands.premium_label(Decimal(p)) for p in ("-0.3", "0", "0.18")),
        *bands.STATUS_REASONS.values(),
        bands.own_band(Decimal(1), [Decimal(1)]).reason or "",
        bands.peer_band(Decimal(1), [], insufficient_set=True).reason or "",
    ]
    assert not [t for t in texts if contains_advice(t)]
    for call in ("NVDA looks cheap", "the stock is expensive", "undervalued vs peers",
                 "over-valued", "a bargain", "richly valued", "attractively valued"):  # fmt: skip
        assert contains_advice(call), call
