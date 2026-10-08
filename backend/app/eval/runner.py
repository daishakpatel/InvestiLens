"""Eval runner (spec §18.5): drive the golden set through the real chat pipeline, compute metrics,
and persist to eval_runs/eval_results. MEASURES Phase 2c/3a/3c — it never re-implements them.

Deterministic metrics (numeric answer accuracy, abstention correctness, citation presence,
hallucination) are meaningful offline. Retrieval Recall@K and LLM-judge faithfulness are only
semantically meaningful with real embeddings/model (ADR-0009/0010, ADR-0020); with mocks they still
compute, but the numbers are not a quality signal.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

import app.repositories.eval_runs as eval_repo
from app.chat.service import answer_question
from app.config import Settings, get_settings
from app.eval.dataset import GoldenQuestion
from app.eval.judge import Judge
from app.eval.metrics import (
    ndcg_at_k,
    numeric_answer_correct,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.eval.resolve import DocKeyResolver
from app.providers.base import LLMClient
from app.rag.pipeline import run_retrieval

_FACTUAL_INTENTS = {
    "FINANCIAL_METRIC",
    "FINANCIAL_EXPLANATION",
    "RISK_ANALYSIS",
    "MANAGEMENT_COMMENTARY",
    "COMPARISON",
}
_SUPPORTED_LABELS = {"supported", "strongly_supported"}


@dataclass
class EvalSummary:
    n: int
    metrics: dict[str, Any]
    per_question: list[tuple[str, dict[str, Any]]] = field(default_factory=list)


def _dedupe(keys: list[str | None]) -> list[str]:
    seen: list[str] = []
    for k in keys:
        if k is not None and k not in seen:
            seen.append(k)
    return seen


def _retrieval_metrics(
    session: Session, q: GoldenQuestion, resolver: DocKeyResolver, settings: Settings, k: int
) -> tuple[dict[str, float], str]:
    """Rank retrieved docs and score them against expected_sources. Returns (metrics, evidence)."""
    try:
        result = run_retrieval(session, question=q.question, ticker=q.company, settings=settings)
    except Exception:
        return {}, ""
    ranked = _dedupe([resolver.key_for(e.document_id) for e in result.evidence])
    relevant = set(q.expected_sources)
    return (
        {
            f"recall_at_{k}": recall_at_k(ranked, relevant, k),
            f"precision_at_{k}": precision_at_k(ranked, relevant, k),
            "mrr": reciprocal_rank(ranked, relevant),
            f"ndcg_at_{k}": ndcg_at_k(ranked, relevant, k),
        },
        result.assembled_context,
    )


def evaluate_question(
    session: Session,
    q: GoldenQuestion,
    *,
    user_id: int,
    llm: LLMClient,
    judge: Judge,
    resolver: DocKeyResolver,
    settings: Settings,
    k: int,
) -> dict[str, Any]:
    started = time.monotonic()
    turn = answer_question(
        session, company=q.company, question=q.question, user_id=user_id, llm=llm, settings=settings
    )
    latency_ms = int((time.monotonic() - started) * 1000)

    answered = not (turn.abstained or turn.refused)
    is_factual = q.intent in _FACTUAL_INTENTS or q.expected_numeric is not None
    m: dict[str, Any] = {
        "intent": q.intent,
        "answered": answered,
        "abstention_correct": answered != q.must_abstain,
        "n_citations": len(turn.citations),
        "evidence_label": turn.evidence_label,
        "latency_ms": latency_ms,
    }

    if q.expected_numeric is not None:
        m["numeric_correct"] = (
            numeric_answer_correct(
                turn.answer, q.expected_numeric.value, q.expected_numeric.tolerance
            )
            if answered
            else False
        )

    if answered and is_factual:
        m["cited_ok"] = turn.evidence_label in _SUPPORTED_LABELS

    # Hallucination: answered a question it should have refused, or asserted a fact uncited.
    m["hallucination"] = (answered and q.must_abstain) or (
        answered and is_factual and not q.must_abstain and len(turn.citations) == 0
    )

    if q.expected_sources:
        retrieval, evidence_text = _retrieval_metrics(session, q, resolver, settings, k)
        m["retrieval"] = retrieval
        # LLM-judge faithfulness: only for answered qualitative (non-numeric) questions.
        if answered and q.expected_numeric is None and is_factual:
            m["faithful"] = judge.grade(
                question=q.question, answer=turn.answer, evidence=evidence_text
            ).faithful

    return m


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _aggregate(results: list[dict[str, Any]], k: int) -> dict[str, Any]:
    def collect(key: str) -> list[float]:
        return [float(r[key]) for r in results if key in r and r[key] is not None]

    retr = [r["retrieval"] for r in results if r.get("retrieval")]
    return {
        "n": len(results),
        "n_answered": sum(1 for r in results if r["answered"]),
        "abstention_accuracy": _mean([1.0 if r["abstention_correct"] else 0.0 for r in results]),
        "numeric_accuracy": _mean(
            [1.0 if r["numeric_correct"] else 0.0 for r in results if "numeric_correct" in r]
        ),
        "citation_accuracy": _mean(
            [1.0 if r["cited_ok"] else 0.0 for r in results if "cited_ok" in r]
        ),
        "hallucination_rate": _mean([1.0 if r["hallucination"] else 0.0 for r in results]),
        "faithfulness": _mean([1.0 if r["faithful"] else 0.0 for r in results if "faithful" in r]),
        f"recall_at_{k}": _mean([r[f"recall_at_{k}"] for r in retr]),
        f"precision_at_{k}": _mean([r[f"precision_at_{k}"] for r in retr]),
        "mrr": _mean([r["mrr"] for r in retr]),
        f"ndcg_at_{k}": _mean([r[f"ndcg_at_{k}"] for r in retr]),
        "avg_latency_ms": _mean(collect("latency_ms")),
    }


def config_hash(settings: Settings, *, judge_version: str) -> str:
    """Stable hash of the knobs that change results, so a run is comparable only to like configs."""
    parts = [
        settings.llm_model_strong,
        settings.llm_model_cheap,
        str(settings.rag_rerank_enabled),
        str(settings.rag_sufficiency_min_score),
        str(settings.citation_partial_policy),
        judge_version,
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def run_eval(
    session: Session,
    questions: list[GoldenQuestion],
    *,
    user_id: int,
    llm: LLMClient,
    judge: Judge,
    settings: Settings | None = None,
    k: int = 5,
) -> EvalSummary:
    settings = settings or get_settings()
    resolver = DocKeyResolver(session)
    per_question: list[tuple[str, dict[str, Any]]] = []
    for q in questions:
        metrics = evaluate_question(
            session,
            q,
            user_id=user_id,
            llm=llm,
            judge=judge,
            resolver=resolver,
            settings=settings,
            k=k,
        )
        per_question.append((q.id, metrics))
    aggregate = _aggregate([m for _id, m in per_question], k)
    return EvalSummary(n=len(questions), metrics=aggregate, per_question=per_question)


def persist_run(
    session: Session,
    summary: EvalSummary,
    *,
    name: str,
    config_hash: str,
    git_sha: str | None,
    status: str = "complete",
) -> int:
    """Store the run + per-question rows; returns the run id."""
    run = eval_repo.create_run(
        session,
        name=name,
        config_hash=config_hash,
        git_sha=git_sha,
        metrics=summary.metrics,
        status=status,
    )
    eval_repo.record_results(session, run_id=run.id, results=summary.per_question)
    return run.id
