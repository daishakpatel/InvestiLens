"""Coverage-closing tests for the deterministic finance helpers (Phase 1c, 100% on finance/)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.finance.concept_map import load_concept_map
from app.finance.periods import duration_days
from app.finance.selection import FactView, matching_facts, rank_restatements, select_metric
from app.finance.validation import (
    check_accounting_identity,
    check_nonnegative,
    check_yoy_jump,
)

_D = Decimal


def test_validation_branches() -> None:
    assert check_accounting_identity(_D(0), _D(1), _D(1)) is None  # assets 0 -> skip
    assert check_accounting_identity(_D(100), _D(60), _D(40)) is None  # balanced
    imbalance = check_accounting_identity(_D(100), _D(10), _D(10))
    assert imbalance is not None and imbalance.issue_code == "ACCOUNTING_IDENTITY"
    assert check_nonnegative("revenue", _D(10)) is None
    negative = check_nonnegative("revenue", _D(-1))
    assert negative is not None and negative.issue_code == "NEGATIVE_VALUE"
    assert check_yoy_jump("revenue", _D(10), _D(0)) is None  # prior 0 -> skip
    assert check_yoy_jump("revenue", _D(11), _D(10)) is None  # within threshold
    jump = check_yoy_jump("revenue", _D(100), _D(10))  # 9x jump
    assert jump is not None and jump.issue_code == "YOY_JUMP"


def test_selection_edge_cases() -> None:
    assert rank_restatements([]) == []
    cmap = load_concept_map(ticker="NVDA")
    assert select_metric([], cmap, "not_a_metric", period_end=date(2025, 1, 1)) is None
    stock_fact = FactView(
        "us-gaap:Assets", None, date(2025, 1, 1), "instant", _D(1), "USD", "acc", date(2025, 2, 1)
    )
    # Period that doesn't match -> empty candidate list (exercises the no-match branch).
    assert (
        matching_facts([stock_fact], "us-gaap:Assets", period_end=date(2024, 1, 1), kind="stock")
        == []
    )
    assert matching_facts(
        [stock_fact], "us-gaap:Assets", period_end=date(2025, 1, 1), kind="stock"
    ) == [stock_fact]


def test_duration_days_handles_none() -> None:
    assert duration_days(None, date(2025, 1, 1)) is None
    assert duration_days(date(2025, 1, 1), date(2025, 1, 1)) == 1


def test_concept_map_defaults() -> None:
    cmap = load_concept_map()  # no company -> defaults, standard sector
    assert cmap.applies("some_unknown_metric") is True  # unknown -> applicable by default
    assert cmap.unit_family("revenue") == "currency"
    assert cmap.unit_family("eps_diluted") == "per_share"
    assert cmap.kind("not_a_metric") is None


def test_canonical_skips_null_fiscal_year_and_flow_instant_mismatch() -> None:
    from app.finance.ratio_builder import _Canonical
    from app.models import FinancialMetric

    rows = [
        FinancialMetric(fiscal_year=None, metric_name="revenue", metric_value=Decimal(1)),
        FinancialMetric(
            fiscal_year=2025, metric_name="revenue", metric_value=Decimal(10), source_id="acc-1"
        ),
    ]
    canonical = _Canonical(rows)
    assert canonical.fiscal_years == [2025]  # the null-year row is skipped
    assert canonical.value(2025, "revenue") == Decimal(10)

    # A flow metric must not match an instant fact (exercises the duration guard).
    instant = FactView(
        "us-gaap:Revenues",
        None,
        date(2025, 1, 1),
        "instant",
        Decimal(1),
        "USD",
        "acc",
        date(2025, 2, 1),
    )
    assert (
        matching_facts([instant], "us-gaap:Revenues", period_end=date(2025, 1, 1), kind="flow")
        == []
    )


def test_jpm_stock_override_loads() -> None:
    cmap = load_concept_map(ticker="JPM", cik="0000019617")
    assert cmap.tags("shares_outstanding") == ["dei:EntityCommonStockSharesOutstanding"]
