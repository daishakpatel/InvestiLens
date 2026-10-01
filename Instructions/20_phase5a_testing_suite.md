# Phase 5a — Testing Suite

**Prerequisites:** ideally most of Phase 1–4 exist to test against, but the suites here (unit,
property-based, contract) should actually be built incrementally alongside every prior phase,
not bolted on at the end. Use this file as the checklist to confirm nothing was skipped, and
to build the suites (integration, E2E, security, resilience, load) that need the full system
running.
**Blocks:** nothing blocks on this structurally, but it's what makes every other phase's
Definition of Done actually verifiable in CI rather than by hand.
**Full spec sections:** §30 (full testing strategy).

## Objective

Make sure every layer of the system is tested the way the spec requires, close any gaps left
by earlier phases, and wire it all into CI.

## Scope

1. **Unit tests — audit and fill gaps:** financial calculations (Phase 1c should already be at
   100% coverage — verify), SEC parsing (Phase 1a/2a), chunking (Phase 2a), citation mapping
   (Phase 3a), API request/response validation (Phase 4a). Add property-based tests
   (Hypothesis) for anything with a mathematical invariant that wasn't already covered:
   growth/CAGR, unit conversions, RRF fusion ordering stability, "no chunk crosses a section
   boundary."
2. **Golden fixture tests:** confirm `golden_metrics.json` exact-match tests (from Phase 0d/1c)
   are wired into CI as a hard gate, not just run manually.
3. **Integration tests:** API → database → retrieval → LLM, using Testcontainers for
   Postgres+pgvector and Redis. LLM and embedding calls use the **recorded fixtures** from
   Phase 0d (VCR-style) or deterministic fakes — never live model calls in the default CI run.
   Provider clients (SEC, price, news) tested against their mocks plus periodic contract tests
   against recorded real responses.
4. **End-to-end test (Playwright)** — the full happy path from spec §30.3:
   ```text
   Search NVDA → load dashboard → generate report → ask question →
   receive citation → open source
   ```
5. **Citation tests (dedicated suite):** unknown source ID rejection, numeric-mismatch
   rejection, correct citation-number rendering order, derivation-lineage correctness — these
   are critical enough to warrant their own test file distinct from general unit tests.
6. **Security tests:** authorization/IDOR (reuse Phase 4b's tests, expand coverage), rate-limit
   enforcement, an injection payload corpus run against filing/news ingestion and against chat
   (reuse Phase 2c/3c's red-team set here as a formal, CI-gated suite), XSS payloads embedded
   in filing/news text rendered safely by the frontend.
7. **Resilience tests:** provider timeouts/500s/429s handled gracefully, Redis down (cache
   miss path still works), LLM returns malformed JSON (repair-then-fallback path triggers
   correctly), partial ingestion failure doesn't cascade.
8. **Load tests (k6 or Locust):** key read endpoints and chat concurrency, checking against the
   NFR latency targets from the main spec (§8) — this is where you actually verify those
   targets rather than just assuming them.
9. **Migration tests:** Alembic upgrade/downgrade against both an empty and a populated
   database (should already exist from Phase 0b — confirm it's still passing).
10. **Accessibility tests:** axe integrated into the Playwright E2E run.
11. **Coverage gate:** 80%+ backend coverage overall, 100% for `finance/` and `citation/`
    modules specifically — wire this as a CI failure condition, not just a report.

## Out of scope for this file

The evaluation framework (Recall@K, citation accuracy, hallucination rate on the golden
question set) is a distinct system — that's `21_phase5b_evaluation_framework.md`. This file is
about conventional software testing; that one is about AI-quality measurement.

## Definition of Done

- [ ] CI runs unit, integration, E2E, security, resilience, and migration suites on every PR
- [ ] Coverage gate enforced: 80%+ overall, 100% on `finance/` and `citation/`
- [ ] The full E2E happy path (search → dashboard → report → chat → citation → source) passes
- [ ] The injection-payload corpus does not break ingestion or chat behavior
- [ ] A simulated provider outage (SEC/price/news/LLM) degrades gracefully per the error
      handling rules in the main spec, verified by an automated test, not manual observation
- [ ] Load test results are recorded and compared against the NFR latency targets
