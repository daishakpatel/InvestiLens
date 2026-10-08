"""A/B comparison harness (spec §18.7): run the same golden set under two configs and diff per
question, so changes ("we switched the reranker and Recall@5 went up") are backed by evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings
from app.eval.dataset import GoldenQuestion
from app.eval.judge import Judge
from app.eval.runner import EvalSummary, run_eval
from app.providers.base import LLMClient

# Per-question metric keys that are booleans worth diffing.
_FLAGS = (
    "answered",
    "abstention_correct",
    "numeric_correct",
    "cited_ok",
    "hallucination",
    "faithful",
)


@dataclass
class QuestionDiff:
    question_id: str
    changed: dict[str, tuple[Any, Any]]  # key -> (a_value, b_value)


@dataclass
class ABResult:
    a: EvalSummary
    b: EvalSummary
    metric_deltas: dict[str, float]  # b - a for each shared aggregate metric
    question_diffs: list[QuestionDiff]


def _metric_deltas(a: dict[str, Any], b: dict[str, Any]) -> dict[str, float]:
    deltas: dict[str, float] = {}
    for key in a.keys() & b.keys():
        av, bv = a[key], b[key]
        if isinstance(av, (int, float)) and isinstance(bv, (int, float)):
            deltas[key] = float(bv) - float(av)
    return deltas


def _question_diffs(a: EvalSummary, b: EvalSummary) -> list[QuestionDiff]:
    b_by_id = dict(b.per_question)
    diffs: list[QuestionDiff] = []
    for qid, am in a.per_question:
        bm = b_by_id.get(qid, {})
        changed = {
            flag: (am.get(flag), bm.get(flag))
            for flag in _FLAGS
            if flag in am and flag in bm and am.get(flag) != bm.get(flag)
        }
        if changed:
            diffs.append(QuestionDiff(question_id=qid, changed=changed))
    return diffs


def run_ab(
    session: Session,
    questions: list[GoldenQuestion],
    *,
    user_id: int,
    llm: LLMClient,
    judge: Judge,
    config_a: Settings,
    config_b: Settings,
    k: int = 5,
) -> ABResult:
    a = run_eval(session, questions, user_id=user_id, llm=llm, judge=judge, settings=config_a, k=k)
    b = run_eval(session, questions, user_id=user_id, llm=llm, judge=judge, settings=config_b, k=k)
    return ABResult(
        a=a,
        b=b,
        metric_deltas=_metric_deltas(a.metrics, b.metrics),
        question_diffs=_question_diffs(a, b),
    )
