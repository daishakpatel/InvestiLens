"""Readable metric text (spec §0: raw values in storage, $M/$B only at display). Pure, offline.

Refs: FR-027 (a metric question is answered from stored figures), DR-041/042 (a missing or
not-applicable value is said to be so, never shown as zero).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.citation.extract import extract_numbers
from app.finance.display import describe_metric, format_metric_value


@pytest.mark.parametrize(
    ("value", "unit", "metric", "expected"),
    [
        ("215938000000.00000000", "USD", "revenue", "$215.94 billion"),
        ("4424900000000", "USD", "total_assets", "$4.42 trillion"),
        ("999000000", "USD", "short_term_debt", "$999 million"),
        ("7500000000", "USD", "long_term_debt", "$7.5 billion"),
        ("548126.5", "USD", "capex", "$548,126.5"),
        ("-147782000000", "USD", "net_income", "-$147.78 billion"),
        ("0.71068084", "ratio", "gross_margin", "71.07%"),
        ("-2.19888476", "ratio", "yoy_growth", "-219.89%"),
        ("3.90526381", "ratio", "current_ratio", "3.91x"),
        ("0.05383584", "ratio", "debt_to_equity", "0.05x"),
        ("4.90000000", "USD/shares", "eps_diluted", "$4.90 per share"),
        ("-4.38", "USD/shares", "eps_diluted", "-$4.38 per share"),
        ("24514000000", "shares", "shares_diluted_weighted", "24.51 billion shares"),
        ("12.5", "widgets", "something_else", "12.5 widgets"),
        ("12.5", None, "something_else", "12.5"),
    ],
)
def test_values_read_the_way_a_person_would_say_them(  # FR-027
    value: str, unit: str | None, metric: str, expected: str
) -> None:
    assert format_metric_value(Decimal(value), unit, metric=metric) == expected


def test_a_missing_value_is_named_not_shown_as_zero() -> None:  # DR-041, DR-042
    assert format_metric_value(None, "USD", metric="gross_margin") == "not available"
    assert describe_metric("gross_margin", "FY2025", None, "ratio") == (
        "Gross margin for FY2025 was not available"
    )


@pytest.mark.parametrize(
    ("name", "period", "value", "unit", "expected"),
    [
        ("revenue", "FY2026", "215938000000", "USD", "Revenue for FY2026 was $215.94 billion"),
        (
            "net_income",
            "Q4-FY2026",
            "42960000000",
            "USD",
            "Net income for Q4 FY2026 was $42.96 billion",
        ),
        (
            "eps_diluted",
            "FY2026",
            "4.9",
            "USD/shares",
            "Diluted EPS for FY2026 was $4.90 per share",
        ),
        ("yoy_growth", "FY2026", "0.65473536", "ratio", "Revenue growth for FY2026 was 65.47%"),
        ("ebitda", "FY2026", "133230000000", "USD", "EBITDA for FY2026 was $133.23 billion"),
    ],
)
def test_metric_sentence(name: str, period: str, value: str, unit: str, expected: str) -> None:
    assert describe_metric(name, period, Decimal(value), unit) == expected  # FR-027


@pytest.mark.parametrize(
    ("value", "unit", "metric"),
    [
        ("215938000000", "USD", "revenue"),
        ("1234567", "USD", "capex"),
        ("0.02798025", "ratio", "capex_intensity"),
        ("24514000000", "shares", "shares_diluted_weighted"),
    ],
)
def test_rounded_text_still_matches_the_stored_value(value: str, unit: str, metric: str) -> None:
    # CIT-005: the verifier re-reads the number out of the sentence, so display rounding must stay
    # inside its 1% tolerance of the stored figure.
    stored = Decimal(value)
    read_back = [t for t in extract_numbers(format_metric_value(stored, unit, metric=metric))]
    assert read_back, "the formatted value must contain a number the verifier can read"
    token = read_back[0]
    assert token.value is not None
    stated = token.value / 100 if token.kind == "percent" else token.value
    assert abs(stated - stored) <= abs(stored) * Decimal("0.01")


def test_valuation_multiples_and_dated_periods() -> None:  # FR-024
    assert format_metric_value(Decimal("46.6342"), "x", metric="pe_ratio") == "46.63x"
    assert describe_metric("pe_ratio", "2026-10-13", Decimal("46.63"), "x") == (
        "Price-to-earnings ratio as of 2026-10-13 was 46.63x"
    )
    assert describe_metric("market_cap", "FY2026", Decimal("5562000000000"), "USD") == (
        "Market cap for FY2026 was $5.56 trillion"
    )
