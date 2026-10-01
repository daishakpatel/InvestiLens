# Architecture

InvestiLens is a **modular monolith**: one FastAPI deployable plus Celery workers, sharing one
PostgreSQL (with pgvector) and Redis ([ADR-0001](decisions/0001-modular-monolith.md)). Source:
spec §19–§20.

## Core engineering flow

Copied from spec §19.2. This separation is the central idea of the project and should not be reworded.

```text
                 ┌───────────────────────┐
                 │       USER            │
                 └───────────┬───────────┘
                             │
                             ▼
                 ┌───────────────────────┐
                 │      RESEARCH API     │
                 └───────────┬───────────┘
                             │
                             ▼
                 ┌───────────────────────┐
                 │     QUERY PLANNER     │
                 └───────────┬───────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        Financial DB    Vector Search    News DB
              │              │              │
              └──────────────┼──────────────┘
                             ▼
                 ┌───────────────────────┐
                 │    EVIDENCE LAYER     │
                 └───────────┬───────────┘
                             │
                             ▼
                 ┌───────────────────────┐
                 │        LLM            │
                 │  Structured Output    │
                 └───────────┬───────────┘
                             │
                             ▼
                 ┌───────────────────────┐
                 │ CITATION VALIDATOR    │
                 └───────────┬───────────┘
                             │
                             ▼
                 ┌───────────────────────┐
                 │    RESEARCH REPORT    │
                 └───────────────────────┘
```

> **That separation is the core of the project.** The database and source documents provide
> the facts; deterministic Python provides the financial calculations; retrieval provides
> evidence; the LLM synthesizes the evidence; the citation layer verifies that the generated
> claims can be traced back to that evidence.

| Layer | Owns | Never does |
|-------|------|------------|
| Deterministic finance (`app/finance/`) | Every number: metrics, ratios, growth, Q4 derivation | Call an LLM |
| Retrieval (`app/rag/`) | Finding evidence; every item carries a backend-issued `source_id` | Generate text |
| LLM (`app/providers/` → `LLMClient`) | Synthesis and explanation of the evidence it is given | Produce numbers, invent sources |
| Citation validator (`app/citation/`) | Checking every claim against its cited source | Pass unverified claims through |

## Life of a research request

1. **Request.** A user asks for a report on `NVDA`. The API router validates input, checks
   auth/quota ([ADR-0005](decisions/0005-jwt-rotating-refresh-tokens.md),
   [ADR-0006](decisions/0006-anonymous-access-policy.md)), creates a `jobs` row, and returns a
   job ID. Progress streams to the client.
2. **Freshness check.** A Celery worker checks `data_freshness`. Stale sources trigger
   ingestion from SEC EDGAR, Tiingo, and Finnhub
   ([ADR-0007](decisions/0007-price-provider-tiingo.md),
   [ADR-0008](decisions/0008-news-provider-finnhub.md)). A failed provider degrades that panel
   visibly; it never blocks the whole report silently.
3. **Deterministic numbers.** The finance layer computes metrics from normalized XBRL facts and
   prices. Each result is registered as a `derived_metric` source with its formula and input
   source IDs.
4. **Query planning.** The planner splits the report into sections and decides, per section,
   what comes from structured data (numbers) and what needs retrieval (narrative evidence).
5. **Retrieval.** Hybrid vector + keyword search over filing chunks and news, fused and
   reranked ([ADR-0002](decisions/0002-pgvector.md),
   [ADR-0003](decisions/0003-custom-rag-orchestration.md)). Every candidate carries a
   `source_id` with a content anchor ([ADR-0004](decisions/0004-citation-anchors.md)).
6. **Evidence layer.** Selected evidence and computed metrics are assembled into a bounded
   context. Filing and news text is wrapped as untrusted data, never instructions.
7. **LLM synthesis.** The strong-tier model returns schema-validated structured output. Each
   claim references source IDs from the evidence set only
   ([ADR-0009](decisions/0009-llm-provider-anthropic.md)).
8. **Citation validation.** The backend checks that every cited ID exists in the evidence set,
   that numbers in prose match computed metrics, and that the claim is supported by the source
   span. Failing claims are removed, not shown.
9. **Report.** The validated report is stored with its model, prompt version, data version,
   and retrieval set (reproducibility, NFR-010), then returned with clickable citations.

## Module boundaries

Business modules: Company, Filings, Financials, News, RAG, Research, Chat, Auth, Watchlist.
Modules talk through service interfaces; no module reads another module's tables except
through that module's repository.

**Layering** (spec §19.4): `api` (routers) → `services` → `repositories` → `models`.
`rag/`, `ingestion/`, `finance/`, `citation/`, `tasks/` are libraries consumed by services.
No business logic in routers; no SQL in services. External systems are reached only through
provider interfaces in `providers/` (`FilingsProvider`, `PriceProvider`, `NewsProvider`,
`LLMClient`, `EmbeddingClient`), each with a mock backed by frozen fixtures.

## Data stores (table names only; columns are designed in Phase 0b)

- **Reference & filings:** `companies`, `company_identifiers`, `fiscal_calendars`,
  `documents`, `filings`, `document_chunks` (pgvector embeddings)
- **Financial data:** `financial_facts`, `financial_metrics`, `price_history`,
  `corporate_actions`, `insider_transactions`, `institutional_holdings`
- **News:** `news`
- **Research & citations:** `research_reports`, `research_sources`, `claim_verifications`,
  `report_feedback`
- **Users:** `users`, `refresh_tokens`, `watchlists`, `watchlist_items`, `alerts`,
  `saved_reports`, `saved_questions`, `chat_sessions`, `chat_messages`
- **Operational:** `ingestion_runs`, `ingestion_dead_letters`, `jobs`, `llm_calls`,
  `retrieval_logs`, `data_quality_issues`, `eval_runs`, `eval_results`, `data_freshness`
- **Redis:** cache, rate limits, Celery broker
- **Object storage** (S3-compatible, MinIO locally): raw filing HTML/PDF

## External dependencies

| Domain | Provider | Decision |
|--------|----------|----------|
| Filings, XBRL, ticker↔CIK | SEC EDGAR (`data.sec.gov`, `sec.gov/Archives`) | Fixed (free, authoritative) |
| Prices | Tiingo | [ADR-0007](decisions/0007-price-provider-tiingo.md) |
| News | Finnhub | [ADR-0008](decisions/0008-news-provider-finnhub.md) |
| LLM | Anthropic Claude | [ADR-0009](decisions/0009-llm-provider-anthropic.md) |
| Embeddings | Voyage AI `voyage-finance-2` | [ADR-0010](decisions/0010-embeddings-voyage-finance.md) |
| Transcripts | None in MVP | [ADR-0011](decisions/0011-transcripts-deferred.md) |
