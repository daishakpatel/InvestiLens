"""Earnings-quality scores and guards (Phase 7d): Beneish, Altman variants, Piotroski criteria,
balance-sheet accruals, the new concept tags' golden values, and the no-accusation rule.

Offline and pure. Requirement IDs: FR-EQ-001 … FR-EQ-015, DR-EQ-001 … DR-EQ-004.
"""

from __future__ import annotations

import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.citation.advice import accuses_on_screening_score, is_screening_source
from app.citation.evidence import EvidenceItem
from app.citation.extract import RawClaim
from app.citation.verify import verify_claim
from app.finance import beneish
from app.finance import metrics as m
from app.finance.concept_map import load_concept_map
from app.finance.facts import fact_views
from app.finance.periods import is_full_year
from app.finance.quality_builder import altman_variant
from app.finance.selection import select_metric
from app.finance.sic import is_manufacturer
from app.ingestion.sec.xbrl import parse_companyfacts
from app.providers.sec.mock import MockSecSource
from app.schemas.sources import DerivedMetricSource

_D = Decimal
_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
_CIK = {"NVDA": "0001045810", "AAPL": "0000320193", "JPM": "0000019617"}

# Prior year (t-1) and current year (t) chosen so every index is exact (see the worked example).
PRIOR = beneish.BeneishYear(
    revenue=_D(1000),
    cost_of_revenue=_D(600),
    receivables=_D(100),
    current_assets=_D(400),
    ppe_net=_D(280),
    total_assets=_D(1000),
    depreciation=_D(70),
    sga_expense=_D(100),
    current_liabilities=_D(200),
    long_term_debt=_D(200),
    net_income=_D(80),
    operating_cash_flow=_D(100),
)
CURRENT = beneish.BeneishYear(
    revenue=_D(1250),
    cost_of_revenue=_D(850),
    receivables=_D(150),
    current_assets=_D(450),
    ppe_net=_D(300),
    total_assets=_D(1250),
    depreciation=_D(100),
    sga_expense=_D(150),
    current_liabilities=_D(300),
    long_term_debt=_D(300),
    net_income=_D(120),
    operating_cash_flow=_D(70),
)


# --- Beneish M-score (FR-EQ-003/004, DR-EQ-002) -------------------------------------------
def test_beneish_worked_example_exact_decimals() -> None:
    """FR-EQ-003. Hand arithmetic:
    DSRI = (150/1250) / (100/1000)            = 0.12 / 0.1   = 1.2
    GMI  = ((1000-600)/1000) / ((1250-850)/1250) = 0.4 / 0.32 = 1.25
    AQI  = (1 - (450+300)/1250) / (1 - (400+280)/1000) = 0.4 / 0.32 = 1.25
    SGI  = 1250 / 1000                                = 1.25
    DEPI = (70/(70+280)) / (100/(100+300))    = 0.2 / 0.25   = 0.8
    SGAI = (150/1250) / (100/1000)            = 0.12 / 0.1   = 1.2
    LVGI = ((300+300)/1250) / ((200+200)/1000) = 0.48 / 0.4  = 1.2
    TATA = (120 - 70) / 1250                                 = 0.04
    M = -4.84 + 0.92*1.2 + 0.528*1.25 + 0.404*1.25 + 0.892*1.25 + 0.115*0.8
        - 0.172*1.2 + 4.679*0.04 - 0.327*1.2
      = -4.84 + 1.104 + 0.66 + 0.505 + 1.115 + 0.092 - 0.2064 + 0.18716 - 0.3924
      = -1.77564   (above -1.78, so "above_threshold")
    """
    result = beneish.beneish_m_score(CURRENT, PRIOR)
    assert result.indices == {
        "dsri": _D("1.2"),
        "gmi": _D("1.25"),
        "aqi": _D("1.25"),
        "sgi": _D("1.25"),
        "depi": _D("0.8"),
        "sgai": _D("1.2"),
        "tata": _D("0.04"),
        "lvgi": _D("1.2"),
    }
    assert result.score == _D("-1.77564")
    assert result.band == beneish.ABOVE
    assert result.metric.value == result.score and result.metric.unit == m.SCORE


def test_beneish_neutral_company_scores_the_intercept_plus_coefficients() -> None:
    """FR-EQ-003: every index 1 and TATA 0 gives -4.84 + 2.36 = -2.48, below the threshold."""
    year = beneish.BeneishYear(**{**vars(PRIOR), "net_income": _D(100)})
    result = beneish.beneish_m_score(year, year)
    assert all(v == 1 for k, v in result.indices.items() if k != "tata")
    assert result.indices["tata"] == 0
    assert result.score == _D("-2.48") and result.band == beneish.BELOW


def test_beneish_missing_input_is_insufficient_and_named() -> None:
    """DR-EQ-002: a missing input names itself and never becomes zero."""
    no_sga = beneish.BeneishYear(**{**vars(PRIOR), "sga_expense": None})
    result = beneish.beneish_m_score(CURRENT, no_sga)
    assert result.band == beneish.INSUFFICIENT and result.score is None
    assert result.missing == ["prior_sga_expense"]
    assert result.metric.value is None and result.metric.warnings == [m.MISSING_INPUT]


def test_beneish_zero_denominator_is_insufficient_and_named() -> None:
    """DR-EQ-002: prior receivables of zero leaves DSRI undefined, named as a zero base."""
    zero = beneish.BeneishYear(**{**vars(PRIOR), "receivables": _D(0)})
    result = beneish.beneish_m_score(CURRENT, zero)
    assert result.band == beneish.INSUFFICIENT
    assert result.missing == ["dsri: zero base"]
    assert result.metric.warnings == [m.NEGATIVE_BASE]


def test_beneish_not_applicable_for_banks() -> None:
    """DR-EQ-001: JPM's sector excludes Beneish (and Altman, Piotroski)."""
    cmap = load_concept_map(ticker="JPM", cik=_CIK["JPM"])
    assert not cmap.applies("beneish") and not cmap.applies("altman")
    result = beneish.beneish_m_score(CURRENT, PRIOR, applicable=cmap.applies("beneish"))
    assert result.band == beneish.NOT_APPLICABLE
    assert result.metric.warnings == [m.NOT_APPLICABLE_SECTOR]


def test_beneish_lineage_carries_each_years_source_ids() -> None:
    """FR-EQ-004: every input keeps its own year's backend-issued source ID."""
    sources = {"revenue": "xbrl:T:revenue:FY2025", "prior_revenue": "xbrl:T:revenue:FY2024"}
    result = beneish.beneish_m_score(CURRENT, PRIOR, sources=sources)
    assert result.source_ids == ["xbrl:T:revenue:FY2025", "xbrl:T:revenue:FY2024"]
    assert len(result.metric.inputs) == 24  # 12 inputs x 2 years


_amount = st.integers(min_value=1, max_value=10**12).map(Decimal)


@settings(max_examples=60, deadline=None)
@given(
    values=st.lists(_amount, min_size=24, max_size=24),
    factor=st.integers(min_value=2, max_value=10**6).map(Decimal),
)
def test_beneish_is_unit_free(values: list[Decimal], factor: Decimal) -> None:
    """DR-EQ-003: scaling every dollar input by the same factor leaves the score unchanged."""
    names = list(beneish.BeneishYear.__dataclass_fields__)
    current = beneish.BeneishYear(**dict(zip(names, values[:12], strict=True)))
    prior = beneish.BeneishYear(**dict(zip(names, values[12:], strict=True)))
    scaled = [
        beneish.BeneishYear(**{k: v * factor for k, v in vars(y).items()}) for y in (current, prior)
    ]
    base, rescaled = beneish.beneish_m_score(current, prior), beneish.beneish_m_score(*scaled)
    assert base.band == rescaled.band or base.score is None
    if base.score is not None and rescaled.score is not None:
        assert abs(base.score - rescaled.score) < _D("1e-18")


# --- Altman variants (FR-EQ-006) ----------------------------------------------------------
def test_altman_original_and_z_double_prime_formulas_and_zones() -> None:
    """FR-EQ-006: coefficients per variant; zones by the variant's own cut-offs."""
    # Original: 1.2*0.2 + 1.4*0.3 + 3.3*0.15 + 0.6*4 + 1.0*0.9 = 0.24+0.42+0.495+2.4+0.9 = 4.455
    z = m.altman_z_score(_D(200), _D(300), _D(150), _D(1000), _D(2000), _D(500), _D(900))
    assert z.value == _D("4.455") and z.formula_id == "altman_z_score"
    # Z'': 6.56*0.2 + 3.26*0.3 + 6.72*0.15 + 1.05*0.4 = 1.312+0.978+1.008+0.42 = 3.718
    z2 = m.altman_z_score(
        _D(200), _D(300), _D(150), _D(1000), _D(200), _D(500), variant="z_double_prime"
    )
    assert z2.value == _D("3.718") and z2.formula_id == "altman_z_double_prime"
    assert [i.name for i in z2.inputs][4] == "book_value_equity"
    assert "sales" not in [i.name for i in z2.inputs]
    assert m.altman_zone(_D("1.80"), "original") == "distress"
    assert m.altman_zone(_D("2.50"), "original") == "grey"
    assert m.altman_zone(_D("3.00"), "original") == "safe"
    assert m.altman_zone(_D("1.80"), "z_double_prime") == "grey"
    assert m.altman_zone(_D("1.00"), "z_double_prime") == "distress"
    assert m.altman_zone(_D("2.61"), "z_double_prime") == "safe"


def test_altman_variant_follows_sic_and_is_recorded() -> None:
    """FR-EQ-006: manufacturers (SIC 20-39) get the original Z; others Z''; never silent."""
    assert is_manufacturer("3674") is True and is_manufacturer("7372") is False
    assert is_manufacturer(None) is None and is_manufacturer("x") is None
    assert altman_variant("3674")[0] == "original"
    variant, basis = altman_variant("7372")
    assert variant == "z_double_prime" and "non-manufacturer" in basis
    assert altman_variant(None) == (
        "z_double_prime",
        "no SIC code: non-manufacturer Z'' (book equity)",
    )


# --- Piotroski (FR-EQ-007) ----------------------------------------------------------------
_STRONG = m.YearFinancials(
    net_income=_D(100),
    operating_cash_flow=_D(120),
    total_assets=_D(1000),
    long_term_debt=_D(100),
    current_assets=_D(500),
    current_liabilities=_D(200),
    shares_diluted=_D(10),
    gross_profit=_D(400),
    revenue=_D(800),
)
_WEAK = m.YearFinancials(
    net_income=_D(50),
    operating_cash_flow=_D(40),
    total_assets=_D(1000),
    long_term_debt=_D(200),
    current_assets=_D(300),
    current_liabilities=_D(200),
    shares_diluted=_D(11),
    gross_profit=_D(300),
    revenue=_D(700),
)


def test_piotroski_exposes_all_nine_criteria() -> None:
    """FR-EQ-007: each test individually, and the total only when all nine are computable."""
    criteria = m.piotroski_criteria(_STRONG, _WEAK)
    assert list(criteria) == list(m.PIOTROSKI_CRITERIA) and len(criteria) == 9
    assert all(criteria.values())  # strong beats weak on every test
    assert m.piotroski_f_score(_STRONG, _WEAK).value == 9
    assert m.piotroski_f_score(_WEAK, _STRONG).value == 2  # only positive NI and positive CFO


def test_piotroski_partial_inputs_report_no_total() -> None:
    """FR-EQ-007: an uncomputable test is None and the total is withheld (n of 9 computable)."""
    no_debt = m.YearFinancials(**{**vars(_STRONG), "long_term_debt": None})
    criteria = m.piotroski_criteria(no_debt, _WEAK)
    assert criteria["falling_leverage"] is None
    assert sum(1 for v in criteria.values() if v is not None) == 8
    result = m.piotroski_f_score(no_debt, _WEAK)
    assert result.value is None and result.warnings == [m.MISSING_INPUT]
    no_shares = m.YearFinancials(**{**vars(_STRONG), "shares_diluted": None})
    assert m.piotroski_criteria(no_shares, _WEAK)["no_share_dilution"] is None
    assert m.piotroski_f_score(_STRONG, _WEAK, applicable=False).warnings == [
        m.NOT_APPLICABLE_SECTOR
    ]


# --- Balance-sheet accruals (FR-EQ-008) ---------------------------------------------------
def test_balance_sheet_accruals_from_net_operating_assets() -> None:
    """FR-EQ-008: NOA = (TA - cash - STI) - (TL - debt); ratio = change / average NOA."""
    prior = m.OperatingBalances(_D(1000), _D(100), _D(100), _D(600), _D(200))  # NOA 400
    current = m.OperatingBalances(_D(1300), _D(100), _D(100), _D(700), _D(200))  # NOA 600
    assert m.net_operating_assets(current) == _D(600)
    assert m.accruals_ratio_balance_sheet(current, prior).value == _D("0.4")  # 200 / 500


def test_balance_sheet_accruals_guards() -> None:
    """DR-EQ-002: securities reported in one year only, or a missing balance, is insufficient."""
    prior = m.OperatingBalances(_D(1000), _D(100), _D(100), _D(600), _D(200))
    one_sided = m.OperatingBalances(_D(1300), _D(100), None, _D(700), _D(200))
    assert m.accruals_ratio_balance_sheet(one_sided, prior).warnings == [m.MISSING_INPUT]
    no_liabilities = m.OperatingBalances(_D(1300), _D(100), _D(100), None, _D(200))
    assert m.net_operating_assets(no_liabilities) is None
    assert m.accruals_ratio_balance_sheet(no_liabilities, prior).warnings == [m.MISSING_INPUT]
    assert m.accruals_ratio_balance_sheet(prior, prior, applicable=False).warnings == [
        m.NOT_APPLICABLE_SECTOR
    ]
    # Neither year holds securities: none held, not missing.
    bare = m.OperatingBalances(_D(1000), _D(100), None, _D(600), _D(200))
    assert m.accruals_ratio_balance_sheet(bare, bare).value == 0


def test_ratio_or_none_guards_zero_and_missing() -> None:
    assert m.ratio_or_none(_D(1), _D(0)) is None
    assert m.ratio_or_none(None, _D(2)) is None
    assert m.ratio_or_none(_D(1), _D(4)) == _D("0.25")


# --- New concept tags: golden values hand-checked against the 10-K (FR-EQ-001) -----------
_NEW_TAGS = (
    "retained_earnings",
    "sga_expense",
    "ppe_net",
    "depreciation",
    "current_assets",
    "current_liabilities",
    "total_liabilities",
    "receivables",
    "income_tax_expense",
)


@pytest.mark.parametrize("ticker", ["NVDA", "AAPL"])
def test_new_concept_tags_match_hand_verified_golden(ticker: str) -> None:
    """FR-EQ-001: each Beneish/Altman input selects the value printed in the latest 10-K."""
    golden = {
        c["ticker"]: c["metrics"]
        for c in json.loads((_FIXTURES / "golden_metrics.json").read_text())["companies"]
    }[ticker]
    rows, _ = parse_companyfacts(1, MockSecSource().companyfacts(_CIK[ticker]))
    facts = fact_views(rows)
    cmap = load_concept_map(ticker=ticker, cik=_CIK[ticker])
    revenue_tags = cmap.tags("revenue")
    annual = [
        f.period_end
        for f in facts
        if f.concept_tag in revenue_tags
        and f.period_end
        and is_full_year(f.period_start, f.period_end)
    ]
    fye_month = Counter(d.month for d in annual).most_common(1)[0][0]
    fye = max(d for d in annual if d.month == fye_month)
    for metric in _NEW_TAGS:
        selection = select_metric(facts, cmap, metric, period_end=fye)
        assert selection is not None, f"{ticker} {metric} not selected"
        assert selection.value == Decimal(golden[metric]["value"]), f"{ticker} {metric}"


def test_depreciation_is_annual_only() -> None:
    """FR-EQ-001: depreciation is a 10-K note figure, so it has no quarters to build or miss."""
    cmap = load_concept_map(ticker="NVDA")
    assert cmap.is_annual_only("depreciation") and not cmap.is_annual_only("sga_expense")
    assert cmap.kind("ppe_net") == "stock" and cmap.kind("sga_expense") == "flow"


# --- No accusation on a screening score (FR-EQ-015) ---------------------------------------
_BENEISH_ID = "derived:NVDA:beneish_m:FY2026"


def _evidence() -> dict[str, EvidenceItem]:
    return {
        _BENEISH_ID: EvidenceItem(
            source=DerivedMetricSource(
                source_id=_BENEISH_ID,
                tier=1,
                formula_id="beneish_m_score",
                formula_version="v1",
                value=_D("-1.16939208"),
                period="FY2026",
            )
        )
    }


def test_accusation_language_on_a_screening_score_is_detected() -> None:
    assert is_screening_source(_BENEISH_ID)
    assert is_screening_source("derived:AAPL:altman_z:FY2025")
    assert not is_screening_source("derived:NVDA:gross_margin:FY2026")
    assert accuses_on_screening_score("NVIDIA is a likely manipulator.", [_BENEISH_ID])
    assert accuses_on_screening_score("This suggests accounting fraud.", [_BENEISH_ID])
    assert not accuses_on_screening_score("The M-score is above the threshold.", [_BENEISH_ID])
    # The same words citing a filing (a risk factor about fraud) are not a score accusation.
    assert not accuses_on_screening_score("We may be exposed to fraud.", ["nvda-10k-p1"])


@pytest.mark.parametrize(
    "text",
    [
        "NVIDIA's Beneish M-score of -1.17 marks it as a manipulator.",
        "The M-score of -1.17 points to earnings manipulation.",
        "An M-score of -1.17 suggests fraud.",
    ],
)
def test_report_sentence_calling_company_a_manipulator_is_blocked(text: str) -> None:
    """FR-EQ-015: the verifier rejects the claim even though its number matches the source."""
    claim = RawClaim(claim_id="c1", text=text, source_ids=[_BENEISH_ID])
    verified = verify_claim(claim, _evidence())
    assert verified.status == "rejected" and verified.reason_code == "OVERREACH"


def test_neutral_sentence_on_the_same_score_is_accepted() -> None:
    claim = RawClaim(
        claim_id="c2",
        text="NVIDIA's Beneish M-score was -1.17.",
        source_ids=[_BENEISH_ID],
    )
    verified = verify_claim(claim, _evidence())
    assert verified.status == "accepted"


def test_prior_shares_fall_back_to_split_adjustment() -> None:
    """FR-EQ-008: without the next 10-K's comparative, the prior count is moved across splits."""
    from datetime import date

    from app.finance.quality_builder import _prior_shares, _Year
    from app.finance.ratio_builder import Canonical
    from app.models import FinancialMetric

    def shares(fy: int, value: int) -> FinancialMetric:
        return FinancialMetric(
            fiscal_year=fy,
            metric_name="shares_diluted_weighted",
            metric_value=_D(value),
            source_id=f"xbrl:T:shares_diluted_weighted:FY{fy}",
        )

    year = _Year(Canonical([shares(2024, 2_500), shares(2025, 24_800)]), 2025)
    ends = {2024: date(2024, 1, 28), 2025: date(2025, 1, 26)}
    fallback = _prior_shares(year, {}, [(date(2024, 6, 10), _D(10))], ends)
    assert fallback.value == _D(25_000) and fallback.basis["split_factor"] == "10"
    assert fallback.source_id == "xbrl:T:shares_diluted_weighted:FY2024"
    restated = _prior_shares(year, {2025: (_D(24_940), "xbrl:42")}, [], ends)
    assert restated.value == _D(24_940) and restated.source_id == "xbrl:42"
    assert restated.basis == {"prior_shares_basis": "restated in the FY2025 10-K"}
    no_dates = _prior_shares(year, {}, [(date(2024, 6, 10), _D(10))], {})
    assert no_dates.value == _D(2_500)  # no year ends: nothing to move across, said in basis
