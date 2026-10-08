"""Golden-set loading + typed access (spec §18.1). File produced by scripts/build_golden.py."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

_GOLDEN_PATH = Path(__file__).resolve().parents[1].parent / "tests" / "eval" / "golden_v0.jsonl"


@dataclass(frozen=True)
class ExpectedNumeric:
    value: Decimal
    tolerance: Decimal  # relative tolerance, e.g. 0.001 = 0.1%


@dataclass(frozen=True)
class GoldenQuestion:
    id: str
    company: str
    question: str
    intent: str
    expected_answer: str
    expected_numeric: ExpectedNumeric | None
    expected_sources: list[str]
    must_abstain: bool
    tags: list[str]


def _numeric(raw: dict[str, Any] | None) -> ExpectedNumeric | None:
    if not raw:
        return None
    return ExpectedNumeric(
        value=Decimal(str(raw["value"])), tolerance=Decimal(str(raw["tolerance"]))
    )


def parse_question(row: dict[str, Any]) -> GoldenQuestion:
    return GoldenQuestion(
        id=str(row["id"]),
        company=str(row["company"]),
        question=str(row["question"]),
        intent=str(row["intent"]),
        expected_answer=str(row["expected_answer"]),
        expected_numeric=_numeric(row.get("expected_numeric")),
        expected_sources=list(row.get("expected_sources", [])),
        must_abstain=bool(row["must_abstain"]),
        tags=list(row.get("tags", [])),
    )


def load_golden(path: Path | None = None) -> list[GoldenQuestion]:
    text = (path or _GOLDEN_PATH).read_text()
    return [parse_question(json.loads(line)) for line in text.splitlines() if line.strip()]
