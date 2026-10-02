# ADR-0014: Deterministic lexical reranker for the MVP, cross-encoder deferred

- **Status:** Accepted
- **Date:** 2026-10-01
- **Spec refs:** §16.4 (RAG-012), Appendix F item 4, ADR-0003

## Problem

RAG-012 reranks the fused top ~40 candidates down to top-K behind a config flag. The spec allows
a cross-encoder or an LLM reranker. A real cross-encoder (e.g. a `sentence-transformers`
cross-encoder) is a heavy ML dependency that downloads model weights at import time, which breaks
the offline unit suite (`PROVIDER_MODE=mock`, no network) and CI. An LLM reranker needs a key and
cannot run offline either. We still need a reranker that is testable now and swappable later.

## Decision

Ship a **deterministic `LexicalReranker` as the default** (`app/rag/rerank.py`), behind a
`Reranker` ABC and a `rag_rerank_enabled` flag. It rescores fused candidates with a transparent,
offline signal — query-term overlap (stemmed) combined with the fusion prior and bounded
tier/recency multipliers — and returns normalized `[0,1]` scores so the sufficiency threshold
(RAG-018) is meaningful. The ABC leaves room for an `LLMReranker` (added in Phase 3 when a key
exists) and, if Phase 5b evals justify it, a cross-encoder reranker as a leaf library (allowed by
ADR-0003). Disabling the flag falls back to pure RRF fusion order for latency comparisons.

## Consequences

The whole pipeline runs and is unit-/integration-tested offline today, with reranking that is
inspectable and reproducible (NFR-010). The cost is that lexical reranking is weaker than a trained
cross-encoder on semantic paraphrase; that gap is measured, not assumed — Phase 5b compares the
lexical default against an LLM/cross-encoder reranker on the golden question set and we switch the
default only if it measurably wins. This resolves Appendix F item 4 for the MVP.
