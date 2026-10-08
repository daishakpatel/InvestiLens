"""Unit tests for the evaluation metrics, judge calibration, gate, and report-level eval.

Pure/offline (Phase 5b, spec §18). Proves the metrics compute correctly so a real run's numbers
can be trusted (DoD #2), and that the CI gate catches a citation-accuracy regression (DoD #4).
Refs: §18.2 (retrieval), §18.4 (judge calibration), §18.6 (gate/EVAL-002), §18.8 (report eval).
"""

from __future__ import annotations

from decimal import Decimal

from app.eval.dataset import load_golden
from app.eval.gate import check_gate
from app.eval.judge import FakeJudge, calibrate
from app.eval.metrics import (
    ndcg_at_k,
    numeric_answer_correct,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.eval.report import evaluate_report
from app.schemas.research import ResearchClaim, ResearchReport, Risk


# --- retrieval metrics (§18.2) --------------------------------------------------------
def test_precision_and_recall_at_k() -> None:
    ranked = ["a", "b", "c", "d"]
    relevant = {"a", "c", "x"}
    assert precision_at_k(ranked, relevant, 4) == 0.5  # 2 of top-4 relevant
    assert recall_at_k(ranked, relevant, 4) == 2 / 3  # 2 of 3 relevant found
    assert recall_at_k(ranked, relevant, 1) == 1 / 3


def test_recall_is_vacuously_one_when_no_relevant() -> None:
    assert recall_at_k(["a"], set(), 5) == 1.0


def test_mrr_uses_first_relevant_rank() -> None:
    assert reciprocal_rank(["x", "y", "a"], {"a"}) == 1 / 3
    assert reciprocal_rank(["a"], {"a"}) == 1.0
    assert reciprocal_rank(["x", "y"], {"a"}) == 0.0


def test_ndcg_is_one_for_ideal_ranking_and_discounts_later_hits() -> None:
    assert ndcg_at_k(["a", "b"], {"a", "b"}, 2) == 1.0
    worse = ndcg_at_k(["x", "a"], {"a"}, 2)
    better = ndcg_at_k(["a", "x"], {"a"}, 2)
    assert better > worse


def test_numeric_answer_match_within_relative_tolerance() -> None:
    # "revenue was 130,497 million" ≈ 130.497B within 0.1%.
    text = "Revenue was 130,497 million for fiscal 2025 [SOURCE:x]."
    assert numeric_answer_correct(text, Decimal("130497000000"), Decimal("0.001"))
    assert not numeric_answer_correct(text, Decimal("99999000000"), Decimal("0.001"))


# --- judge calibration (§18.4) --------------------------------------------------------
def test_calibration_agreement_and_target() -> None:
    judge = [True, True, False, True]
    human = [True, False, False, True]
    result = calibrate(judge, human, target=0.85)
    assert result.n == 4 and result.agreement == 0.75 and not result.meets_target
    assert calibrate([True, False], [True, False]).meets_target  # 100% agreement


def test_fake_judge_is_deterministic() -> None:
    j = FakeJudge()
    assert j.grade(question="q", answer="cited [1]", evidence="e").faithful
    assert not j.grade(question="q", answer="no citation", evidence="e").faithful


# --- CI gate / EVAL-002 (§18.6) -------------------------------------------------------
def test_gate_passes_when_metrics_hold_or_improve() -> None:
    baseline = {"recall_at_5": 0.80, "citation_accuracy": 0.95, "hallucination_rate": 0.01}
    current = {"recall_at_5": 0.81, "citation_accuracy": 0.95, "hallucination_rate": 0.01}
    assert check_gate(current, baseline).passed


def test_gate_fails_on_citation_accuracy_regression() -> None:
    # The DoD "deliberately break it" check: citation accuracy drops > 1 point → gate fails.
    baseline = {"citation_accuracy": 0.95, "hallucination_rate": 0.01}
    current = {"citation_accuracy": 0.90, "hallucination_rate": 0.01}
    result = check_gate(current, baseline)
    assert not result.passed
    assert any("citation_accuracy" in f for f in result.failures)


def test_gate_fails_on_hallucination_rise_and_recall_drop() -> None:
    baseline = {"recall_at_5": 0.80, "hallucination_rate": 0.01}
    current = {"recall_at_5": 0.70, "hallucination_rate": 0.03}
    result = check_gate(current, baseline)
    assert not result.passed and len(result.failures) == 2


def test_gate_skips_metrics_missing_on_either_side() -> None:
    # Offline runs have no meaningful recall → absent → not a failure.
    assert check_gate({"citation_accuracy": 0.95}, {"citation_accuracy": 0.95}).passed


# --- report-level eval (§18.8) --------------------------------------------------------
def _claim(cid: str) -> ResearchClaim:
    return ResearchClaim(claim_id=cid, text="Revenue grew.", source_ids=["s1"])


def test_report_eval_completeness_and_rejection_rate() -> None:
    report = ResearchReport(
        executive_summary=[_claim("c1")],
        company_overview=[_claim("c2")],
        revenue_analysis=[_claim("c3")],
        profitability_analysis=[],
        balance_sheet_analysis=[],
        cash_flow_analysis=[],
        valuation_analysis=[],
        news_summary=[],
        risks=[Risk(category="supply_chain", description="r", source_ids=["s2"])],
        management_commentary=[],
        bull_factors=[],
        bear_factors=[],
        insufficient_evidence_sections=["valuation_analysis"],
    )
    result = evaluate_report(report, accepted_claims=9, rejected_claims=1, latency_ms=1200)
    assert result.total_claims == 4  # 3 claims + 1 risk
    assert result.citation_coverage == 1.0  # schema guarantees every claim cites (invariant)
    assert result.section_completeness == 4 / 12  # exec, overview, revenue, risks
    assert result.rejected_claim_rate == 0.1 and result.latency_ms == 1200


# --- dataset integrity ----------------------------------------------------------------
def test_golden_dataset_loads_and_has_coverage() -> None:
    questions = load_golden()
    assert len(questions) >= 100
    assert any(q.must_abstain for q in questions)
    assert any(q.expected_numeric is not None for q in questions)
    assert {q.intent for q in questions} >= {
        "FINANCIAL_METRIC",
        "RISK_ANALYSIS",
        "PROMPT_INJECTION",
    }
