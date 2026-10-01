# InvestiLens — Agent Task Index

This folder breaks the full spec (`InvestiLens_Spec_v2.md`) into small, sequential task
files. Give an agent **one file at a time**, in the order below. Each file is scoped to be
finishable in a single agent session and states exactly what it needs from prior files and
what it must hand off to later ones.

If a task file references "the full spec," that means `InvestiLens_Spec_v2.md` — keep it in
the repo (`docs/InvestiLens_Spec_v2.md`) as the reference doc; these task files are the
condensed, actionable version of it.

## How to use these files

1. Work top to bottom. Don't start a file whose "Prerequisites" aren't done.
2. Give the agent **only** its task file (plus the repo as it currently stands). Don't paste
   the whole spec — that's what causes agents to lose focus or run out of context.
3. Each file ends with a **Definition of Done** checklist. Don't move to the next file until
   every box is checkable.
4. If an agent needs a decision the file doesn't make (e.g. "which price provider"), check
   `docs/decisions/` first; if it's not decided yet, make the call, write a one-paragraph ADR,
   and continue — don't block on it.
5. Global conventions (apply to every file, not restated each time):
   - Money stored as raw USD `NUMERIC`, never float. Convert to $M/$B only at display time.
   - Dates: ISO-8601, UTC in storage, fiscal period fields separate from calendar dates.
   - Every external call (SEC, price, news, LLM) needs timeout + retry + logging + a mock.
   - No LLM-generated financial numbers, ever. No AI claim without a source ID.
   - Every schema/API/DB change updates the matching doc in the same PR.

## Reading order

### Phase 0 — Contracts (build once, before anything else)
- `01_phase0a_architecture_and_adrs.md`
- `02_phase0b_database_schema.md`
- `03_phase0c_api_contracts.md`
- `04_phase0d_fixtures_and_mocks.md`

### Phase 1 — Data Foundation
- `05_phase1a_sec_ingestion.md`
- `06_phase1b_xbrl_concept_map.md`
- `07_phase1c_financial_metrics.md`
- `08_phase1d_price_ingestion.md`
- `09_phase1e_news_ingestion.md`

### Phase 2 — Documents & Retrieval
- `10_phase2a_document_parsing_chunking.md`
- `11_phase2b_embeddings_and_indexes.md`
- `12_phase2c_rag_retrieval_pipeline.md`

### Phase 3 — AI Generation
- `13_phase3a_citation_system.md`
- `14_phase3b_research_report_generation.md`
- `15_phase3c_chat_qa.md`

### Phase 4 — API & Frontend
- `16_phase4a_fastapi_endpoints.md`
- `17_phase4b_auth_and_users.md`
- `18_phase4c_frontend_dashboard.md`
- `19_phase4d_frontend_report_and_chat.md`

### Phase 5 — Quality & Ops
- `20_phase5a_testing_suite.md`
- `21_phase5b_evaluation_framework.md`
- `22_phase5c_observability_and_security.md`
- `23_phase5d_devops_and_deployment.md`

### Phase 6 — Advanced (optional, do after MVP is live)
- `24_phase6a_comparison_and_portfolio.md`
- `25_phase6b_filing_diff_and_mgmt_tracking.md`

## Dependency map (who blocks whom)

```text
Phase 0 (all 4 files) ─┬─> Phase 1a SEC Ingestion ─┬─> Phase 1b Concept Map ─> Phase 1c Metrics
                        │                            └─> Phase 2a Chunking ─> Phase 2b Embeddings ─> Phase 2c RAG
                        ├─> Phase 1d Prices ─────────────────────────────────────────────┤
                        ├─> Phase 1e News ────────────────────────────────────────────────┤
                        ├─> Phase 3a Citations ───────────────────────────────────────────┤
                        │                                                                  ▼
                        │                                                    Phase 3b Report Gen ─> Phase 3c Chat
                        ├─> Phase 4b Auth                                                  │
                        └─> Phase 4a FastAPI (stub against mocks, fill in as above land) ───┘
                                                                                             │
                        Phase 4c/4d Frontend (build against mocked API early) ───────────────┘
                        Phase 5 (testing/eval/observability/devops) — start early, finish last
                        Phase 6 — after Definition of Done in the master spec (§36) is met
```

You can run Phase 1d, 1e, 3a, and 4b in parallel with Phase 1a–1c since they don't depend on
each other. Everything converges at Phase 3b (report generation) and Phase 4a (API).
