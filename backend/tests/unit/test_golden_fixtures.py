"""Golden fixture structure tests (Phase 0d DoD). Offline."""

from __future__ import annotations

import json
from pathlib import Path

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

REQUIRED_METRICS = {"revenue", "net_income", "eps_diluted", "gross_margin"}
REQUIRED_Q_FIELDS = {
    "id",
    "company",
    "question",
    "intent",
    "expected_answer",
    "expected_numeric",
    "expected_sources",
    "must_abstain",
    "tags",
}


def test_golden_metrics_cover_all_companies() -> None:
    data = json.loads((_FIXTURES / "golden_metrics.json").read_text())
    companies = {c["ticker"]: c for c in data["companies"]}
    assert {"NVDA", "AAPL", "JPM"} <= companies.keys()
    for company in companies.values():
        assert company["metrics"].keys() >= REQUIRED_METRICS
    # DR-001: a bank has no gross margin.
    assert companies["JPM"]["metrics"]["gross_margin"]["value"] is None
    # A non-bank does.
    assert companies["NVDA"]["metrics"]["gross_margin"]["value"] is not None


def test_golden_questions_shape_and_coverage() -> None:
    rows = [
        json.loads(line)
        for line in (_FIXTURES.parent / "eval" / "golden_v0.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert len(rows) >= 10
    for row in rows:
        assert row.keys() >= REQUIRED_Q_FIELDS, f"missing fields in {row.get('id')}"
    intents = {r["intent"] for r in rows}
    assert "FINANCIAL_METRIC" in intents
    assert "QUALITATIVE_EXPLANATION" in intents
    assert any(r["must_abstain"] for r in rows)  # at least one abstain case
