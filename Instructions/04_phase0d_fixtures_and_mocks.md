# Phase 0d — Frozen Fixtures & Mock Providers

**Prerequisites:** `03_phase0c_api_contracts.md` done (provider interfaces exist to mock
against).
**Blocks:** every task file that touches ingestion, RAG, or generation — they all test against
these fixtures instead of live APIs, and CI depends on this to avoid network calls.
**Full spec sections:** §7 (data providers, DR-004 "mock provider for every interface"), §30.2
(integration tests use recorded fixtures, not live LLM calls), §18.1 (golden question set).

## Objective

Build a small, frozen, offline dataset plus mock implementations of every provider interface,
so every later agent (and CI) can develop and test deterministically without hitting SEC,
a price API, a news API, or a real LLM.

## Scope

1. **Pick 2–3 seed companies** (NVDA, AAPL, and JPM — JPM matters because it exercises
   sector-applicability edge cases downstream). For each:
   - Download and freeze the actual filing HTML for the latest 10-K, one 10-Q, and one 8-K
     from EDGAR (respect the SEC fair-access User-Agent rule from ADR — even a one-time manual
     download should use a descriptive User-Agent).
   - Download and freeze the XBRL `companyfacts` JSON for that company.
   - Freeze ~2 weeks of daily price history (open/high/low/close/volume).
   - Freeze a small sample (10–20 items) of news headlines/descriptions.
   - Hand-verify a small set of "golden" metrics (revenue, net income, EPS, gross margin) for
     each company directly against the filing — this becomes `golden_metrics.json`, used for
     exact-match tests all the way through Phase 1c.
2. **Store fixtures** under `backend/tests/fixtures/` — organize by company and source type
   (`fixtures/nvda/10k_2025.html`, `fixtures/nvda/companyfacts.json`,
   `fixtures/nvda/prices.csv`, `fixtures/nvda/news.json`, `fixtures/golden_metrics.json`).
3. **Implement mock providers** in `backend/app/providers/mocks/` — one per interface from
   Phase 0c (`FilingsProvider`, `PriceProvider`, `NewsProvider`, `LLMClient`,
   `EmbeddingClient`). Each mock reads from the frozen fixtures and returns data shaped exactly
   like the real provider would (same Pydantic response models). A config flag
   (`PROVIDER_MODE=mock|live`) switches between mock and real implementations everywhere.
4. **Record a handful of real LLM responses** (once a real LLM key is available) for a few
   fixed prompts, so Phase 3 tests can replay them (VCR-style) instead of calling a live model
   in every CI run. Store under `backend/tests/fixtures/llm_recordings/`.
5. **Seed the golden question set** (`backend/tests/eval/golden_v0.jsonl`) with an initial 10–15
   questions per spec §18.1's format (`id, company, question, intent, expected_answer,
   expected_numeric, expected_sources, must_abstain, tags`). This will grow in Phase 5b — you're
   just planting it now so later work has something to run against.
6. **CI rule**: unit and integration tests run with `PROVIDER_MODE=mock` only; no real network
   calls are allowed in the default test suite.

## Out of scope for this file

Don't build the real SEC client, parser, or ingestion pipeline yet (Phase 1a). Don't write the
real chunker (Phase 2a). This file only produces frozen inputs and interface-shaped fakes.

## Definition of Done

- [ ] Frozen fixtures exist for 3 companies: filing HTML, XBRL companyfacts, price history,
      news sample
- [ ] `golden_metrics.json` has hand-verified revenue/net income/EPS/gross margin for all 3
      companies, cross-checked against the actual filings
- [ ] A mock implementation exists for every provider interface and returns schema-valid
      responses
- [ ] `PROVIDER_MODE=mock` is the CI default; a test asserts no outbound network call happens
      in the mock test run
- [ ] `golden_v0.jsonl` exists with at least 10 questions covering metric lookup, qualitative
      explanation, and one "should abstain" case
