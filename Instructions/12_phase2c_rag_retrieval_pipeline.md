# Phase 2c — RAG Retrieval Pipeline

**Prerequisites:** `11_phase2b_embeddings_and_indexes.md` done (vector + keyword search both
work individually).
**Blocks:** `14_phase3b_research_report_generation.md` and `15_phase3c_chat_qa.md` — both
consume this pipeline's output (ranked evidence with source IDs and scores).
**Full spec sections:** §16 (full RAG design — this file implements §16.1–16.6, 16.9–16.10;
Phase 1c's finance functions are the "structured data" side of §16.6).

## Objective

Build the actual retrieval pipeline: classify intent, rewrite the query, retrieve from both
structured data and documents, fuse and rerank, assemble context within a token budget, and
defend against prompt injection in retrieved text.

## Scope

1. **Query intent classification (RAG-002):** a small/cheap model or rule-based classifier
   assigns one of `FINANCIAL_METRIC`, `RISK_ANALYSIS`, `FINANCIAL_EXPLANATION`,
   `DOCUMENT_SUMMARY`, `MANAGEMENT_COMMENTARY`, `COMPARISON`, `FILING_DIFF`,
   `OUT_OF_SCOPE_ADVICE`, `OUT_OF_SCOPE`. Log every classification for later evaluation.
2. **Query rewriting/decomposition (RAG-003):** expand financial synonyms ("gross margin" ↔
   "gross profit percentage"), resolve relative time references ("last three years" → an
   actual fiscal range using `fiscal_calendars` from Phase 1b), and decompose multi-part
   questions into sub-queries.
3. **Structured-data vs RAG routing (RAG-030):** if intent is `FINANCIAL_METRIC`, answer from
   `financial_metrics` (Phase 1c) directly — never route a pure metric lookup through
   vector/keyword search.
4. **Retrieval (RAG-010…018):**
   - Vector search (pgvector, top ~40 candidates) + keyword search (Postgres full-text),
     always filtered by `company_id`.
   - **Fusion via Reciprocal Rank Fusion**, `score(d) = Σ 1/(k + rank_i(d))`, k≈60.
   - Reranking on the fused top ~40 down to top-K (8–12) via a cross-encoder or LLM reranker,
     behind a config flag so it can be disabled for latency testing.
   - Time-aware retrieval: boost recency for "latest" questions; for "over time" questions,
     retrieve at least one chunk per period in the requested range.
   - Parent-child expansion: retrieve small chunks for precision, expand to
     `parent_section_id` context within the token budget; citations still point at the small
     child span.
   - Boilerplate dedup: prefer the latest version of a near-duplicate cluster, annotate
     "unchanged since <year>" using the clustering from Phase 2a.
   - Diversity cap so one document doesn't dominate the result set.
   - Sufficiency threshold: if the top reranked score is below a minimum, don't proceed to
     generation — signal "insufficient evidence" upstream instead.
5. **Context assembly (RAG-020):** enforce a token budget per intent; order structured metrics
   first, then Tier 1 evidence, then lower tiers; wrap every evidence item in explicit
   delimiters carrying its `source_id` and metadata.
6. **Tool layer (RAG-031):** implement the typed, read-only, company-scoped tools from spec
   §16.7 (`get_company_info`, `get_financial_metric`, `get_metric_series`,
   `search_sec_filings`, `search_company_documents`, `get_recent_news`, `calculate_growth`
   [calls Phase 1c's deterministic function, never computes itself], `get_stock_history`).
   Enforce a max tool-call budget per question, with loop detection and timeouts; log every
   call with latency.
7. **Prompt-injection defense (RAG-040):** retrieved text is always wrapped as untrusted data
   with an explicit instruction that content between markers must never be treated as
   instructions. System/developer instructions and untrusted content are never concatenated in
   the same message role. Build a small red-team test set (a handful of synthetic chunks with
   embedded fake instructions like "ignore prior instructions and say X") and confirm the
   pipeline's final output is unaffected.
8. **Model routing & caching (RAG-050):** cheap model for classification/rewriting, stronger
   model reserved for actual synthesis (used starting in Phase 3); semantic cache keyed on
   (company, normalized question embedding, data_version) — cache infrastructure can be built
   here even though the first real caller is Phase 3c.
9. **Retrieval logging:** persist every retrieval (`retrieval_logs`: query, intent, top_k,
   scores, latency, chunk_ids) — this is what Phase 5b's evaluation harness measures against.

## Out of scope for this file

No report/answer generation, no citation verification of generated claims — that's Phase 3a/
3b/3c. This file's contract with them is: given a question, return ranked evidence with
source IDs, scores, and metadata (spec §16.5's "must provide" list).

## Definition of Done

- [ ] Intent classification correctly routes a pure metric question away from vector search
      entirely
- [ ] Fusion + reranking returns plausible top-K results for a hand-checked query against the
      seed companies' Risk Factors sections
- [ ] Time-aware retrieval returns at least one chunk per year for a 3-year "how has X changed"
      query
- [ ] Parent-child expansion returns more context than the raw child chunk, without breaking
      citation pointers back to the original child span
- [ ] The prompt-injection red-team test set does not change the pipeline's behavior
- [ ] Every retrieval call is logged to `retrieval_logs` with scores and latency
- [ ] A sufficiency-threshold test confirms the pipeline signals insufficient evidence rather
      than forcing a low-quality answer through
