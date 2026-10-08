"""Top-level RAG retrieval pipeline (RAG-001, §16.1).

Orchestrates: classify intent → rewrite/decompose → route (structured vs documents) → retrieve →
assemble context → log. Its contract with Phase 3 is a `RetrievalResult`: ranked evidence with
backend-issued source IDs, scores, and metadata, plus a sufficiency signal (it never generates an
answer — that is Phase 3a/3b/3c). Out-of-scope and advice questions abstain before any retrieval.
"""

from __future__ import annotations

import re
import time

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.observability.metrics import record_retrieval_score
from app.observability.tracing import span
from app.rag.assembly import assemble_context
from app.rag.intent import classify_intent
from app.rag.retrieval import retrieve_evidence
from app.rag.rewrite import rewrite_query
from app.rag.tools import ToolRunner
from app.rag.types import Evidence, Intent, RetrievalResult, RewrittenQuery
from app.repositories import companies as company_repo
from app.repositories import fiscal as fiscal_repo
from app.repositories import retrieval_logs as log_repo

_ABSTAIN_INTENTS = {Intent.OUT_OF_SCOPE, Intent.OUT_OF_SCOPE_ADVICE}

# Map question phrasing → canonical `financial_metrics.metric_name` for routing (RAG-030).
_METRIC_LEXICON: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bgross margin\b", re.I), "gross_margin"),
    (re.compile(r"\boperating margin\b", re.I), "operating_margin"),
    (re.compile(r"\bnet margin\b", re.I), "net_margin"),
    (re.compile(r"\boperating income\b", re.I), "operating_income"),
    (re.compile(r"\b(free cash flow|fcf)\b", re.I), "free_cash_flow"),
    (re.compile(r"\bebitda\b", re.I), "ebitda"),
    (re.compile(r"\b(net income|earnings|profit)\b", re.I), "net_income"),
    (re.compile(r"\b(revenue|sales|top line)\b", re.I), "revenue"),
]


def _extract_metric(question: str) -> str | None:
    for pattern, name in _METRIC_LEXICON:
        if pattern.search(question):
            return name
    return None


def _structured_answer(
    session: Session, *, ticker: str, metric: str | None, years: list[int]
) -> tuple[list[str], list[str], list[dict[str, object]]]:
    """Answer a pure metric question from `financial_metrics` → (blocks, ids, tool_trace)."""
    if metric is None or not years:
        # No resolvable metric or period → caller abstains rather than guessing (RAG-018).
        return [], [], []
    runner = ToolRunner(session)
    blocks: list[str] = []
    source_ids: list[str] = []
    for period in (f"FY{y}" for y in years):
        result = runner.call("get_financial_metric", ticker=ticker, metric=metric, period=period)
        if result.get("value") is not None:
            blocks.append(
                f"[metric] {metric} {period} = {result['value']} {result.get('unit', '')} "
                f"(source_id={result['source_ids'][0] if result['source_ids'] else 'n/a'})"
            )
            source_ids.extend(result["source_ids"])
    trace = [{"tool": c.name, "latency_ms": c.latency_ms} for c in runner.log]
    return blocks, source_ids, trace


def run_retrieval(
    session: Session,
    *,
    question: str,
    ticker: str,
    request_id: str | None = None,
    settings: Settings | None = None,
) -> RetrievalResult:
    """Run the full retrieval pipeline for one question against one company (§16.1).

    Wrapped in an OTel span (OBS-001, ADR-0021) carrying `company`; `intent` is added once known
    so the full "life of a question" (API → retrieval → LLM → citation validator) is traceable by
    `request_id` even though intent classification happens inside the pipeline, not before it.
    """
    with span("rag.run_retrieval", tracer_name=__name__, attributes={"company": ticker}) as sp:
        result = _run_retrieval(
            session, question=question, ticker=ticker, request_id=request_id, settings=settings
        )
        sp.set_attribute("intent", result.intent.value)
        return result


def _run_retrieval(
    session: Session,
    *,
    question: str,
    ticker: str,
    request_id: str | None,
    settings: Settings | None,
) -> RetrievalResult:
    settings = settings or get_settings()
    started = time.monotonic()
    intent_res = classify_intent(question)
    intent = intent_res.intent

    empty_rewrite = RewrittenQuery(original=question, expanded=question)

    def _log(result: RetrievalResult, top_score: float) -> RetrievalResult:
        latency_ms = int((time.monotonic() - started) * 1000)
        log_repo.record_retrieval(
            session,
            query=question,
            intent=result.intent.value,
            top_k=len(result.evidence),
            scores={
                "intent_confidence": intent_res.confidence,
                "intent_rule": intent_res.rule,
                "top_score": top_score,
                "sufficient": result.sufficient,
            },
            latency_ms=latency_ms,
            chunk_ids=[e.source_id for e in result.evidence] + result.structured_source_ids,
            request_id=request_id,
        )
        record_retrieval_score(intent=result.intent.value, top_score=top_score)
        return result

    # Out-of-scope / advice: abstain before any retrieval (RAG-040, §16.2).
    if intent in _ABSTAIN_INTENTS:
        reason = "out_of_scope_advice" if intent == Intent.OUT_OF_SCOPE_ADVICE else "out_of_scope"
        return _log(
            RetrievalResult(
                question=question,
                intent=intent,
                rewritten=empty_rewrite,
                evidence=[],
                sufficient=False,
                abstain_reason=reason,
            ),
            0.0,
        )

    company = company_repo.get_by_ticker(session, ticker)
    if company is None:
        return _log(
            RetrievalResult(
                question=question,
                intent=intent,
                rewritten=empty_rewrite,
                evidence=[],
                sufficient=False,
                abstain_reason="unknown_company",
            ),
            0.0,
        )

    fiscal_years = fiscal_repo.get_fiscal_years(session, company_id=company.id)
    rewritten = rewrite_query(question, intent=intent, available_fiscal_years=fiscal_years)

    # RAG-030: a pure metric lookup is answered from structured data, never via document search.
    if intent == Intent.FINANCIAL_METRIC:
        # Default a metric lookup with no explicit period to the latest fiscal year.
        years = rewritten.fiscal_years or ([max(fiscal_years)] if fiscal_years else [])
        blocks, source_ids, trace = _structured_answer(
            session, ticker=ticker, metric=_extract_metric(question), years=years
        )
        assembled = assemble_context(intent=intent, evidence=[], structured_blocks=blocks)
        sufficient = bool(source_ids)
        result = RetrievalResult(
            question=question,
            intent=intent,
            rewritten=rewritten,
            evidence=[],
            structured_source_ids=source_ids,
            assembled_context=assembled.context_block,
            sufficient=sufficient,
            abstain_reason=None if sufficient else "no_structured_metric",
            tool_trace=trace,
        )
        return _log(result, 1.0 if sufficient else 0.0)

    # Document intents: hybrid retrieval → fusion → rerank → assemble.
    outcome = retrieve_evidence(
        session, company_id=company.id, rewritten=rewritten, settings=settings
    )
    evidence: list[Evidence] = outcome.evidence
    assembled = assemble_context(intent=intent, evidence=evidence, structured_blocks=[])
    result = RetrievalResult(
        question=question,
        intent=intent,
        rewritten=rewritten,
        evidence=evidence,
        assembled_context=assembled.context_block,
        sufficient=outcome.sufficient,
        abstain_reason=None if outcome.sufficient else "insufficient_evidence",
        tool_trace=[{"tool": "search_company_documents", "latency_ms": None}],
    )
    return _log(result, outcome.top_score)
