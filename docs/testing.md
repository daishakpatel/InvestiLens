# Testing Strategy

How InvestiLens is tested, what runs where, and how to run each suite. Source: spec §30 (testing
strategy) and §8 (NFR latency targets); decisions in [ADR-0019](decisions/0019-testing-strategy-and-ci-gates.md).

## Tiers

| Tier | Suites | Where | Gate? |
|------|--------|-------|-------|
| **1 — per-PR** | ruff + mypy --strict, backend pytest (unit + integration + migration) under coverage, frontend eslint + tsc + Vitest, frontend build | `make check` locally; `ci.yml` on every push/PR | **Yes** (merge gate) |
| **2 — on-demand** | Playwright E2E happy path + axe accessibility | `e2e/`; `e2e.yml` (`workflow_dispatch`) | No |
| **3 — on-demand** | Locust load test vs NFR latency targets | `load/`; run against a deployed stack | No |

Tier 1 is fully offline and reproducible (`PROVIDER_MODE=mock`, no network, DR-004). Tiers 2–3
need a running, seeded stack (and, for a full E2E, an LLM key or the Fake-LLM seed), so they are
not on the per-PR path — see ADR-0019 for why.

## Backend suites (`backend/tests/`)

Every test references at least one requirement ID (conventions.md). Highlights:

- **Unit — financial formulas** (`unit/test_metrics.py`): 100% of `app/finance/metrics.py`; golden
  exact-match (NVDA/AAPL/JPM), reason codes (DR-041), sector applicability (DR-042), lineage
  (DR-040), plus Hypothesis invariants (CAGR/YoY/margin/division).
- **Unit — property invariants** (`unit/test_properties.py`): RRF fusion is deterministic,
  commutative, sorted, and preserves ids (RAG-011); no chunk ever crosses a section boundary
  (CH-001).
- **Unit — citation** (`unit/test_citation.py`, `unit/test_citation_coverage.py`): the five-layer
  verifier (CIT-005) — unknown-source rejection, numeric match/mismatch + tolerance, causal
  over-reach, coverage; first-appearance numbering (CIT-006); tiers (§15); every reference-label
  and resolver branch (→ 100% of `app/citation`).
- **Unit — security corpus** (`unit/test_security_corpus.py`): a corpus of prompt-injection and
  XSS payloads run through the untrusted-content defenses — hidden-markup stripping (DP-004),
  delimiter/control-char neutralization and data-wrapping (RAG-040), and proof that script/XSS
  markup never survives into chunk text.
- **Unit — resilience** (`unit/test_resilience.py`): provider 429/500/timeout → retry+backoff →
  single typed `HttpClientError` (DR-002); transient failure then recovery; malformed LLM JSON →
  one repair → section marked insufficient, never a crash (§17.2).
- **Integration** (`integration/`): API → DB → retrieval → report/chat against real
  Postgres 16 + pgvector; auth + IDOR (AUTH-004/SEC-007); partial-ingestion isolation and
  dead-lettering (`test_sec_ingestion.py::test_partial_failure_is_dead_lettered`); per-section
  report isolation (`test_report_generation.py::test_section_failure_isolated`); migrations
  up/down on empty and populated DBs (`test_migrations.py`). These skip when no Postgres is
  reachable (offline), and run in CI via the `pgvector/pgvector:pg16` service.

LLM/embedding calls use deterministic fakes/recorded fixtures (Phase 0d) — never live models in
the default run.

### Observability & security (Phase 5c, §28/§29)

- **Unit — tracing** (`unit/test_tracing.py`): OTel spans actually carry the attributes OBS-001
  requires, asserted via `InMemorySpanExporter` (no collector running).
- **Unit — error handling** (`unit/test_error_handling.py`): the catch-all exception handler
  never leaks a stack trace or exception detail into an RFC 7807 response (ERR-003).
- **Unit — rate limiting** (`unit/test_rate_limit.py`): the in-process and Redis-backed (via
  `fakeredis`) limiters, plus the middleware's two tiers (general vs AI) end to end.
- **Unit — billing** (`unit/test_billing_cost.py`): LLM cost estimation is `Decimal`, scales with
  model tier, never negative.
- **Integration — alerts** (`integration/test_alerts.py`): each of the five DB-driven alert rules
  fires on a seeded "simulated failure" and stays silent on healthy state (the DoD's explicit
  "alerts fire correctly in a simulated failure" requirement, testable with no Prometheus
  running).
- **Integration — budget/IDOR/retention/injection** (`integration/test_chat.py`,
  `integration/test_report_generation.py`, `integration/test_auth.py`,
  `integration/test_api_endpoints.py`, `integration/test_injection_production_shaped.py`): AI
  budget enforcement blocks the LLM-cost path only (metric answers stay free); `/alerts` is now
  IDOR-tested like watchlists/chat sessions; `hard_delete_user` cascades to owned data but keeps
  public reports (`user_id` nulled); the Phase 2c/3c red-team corpus re-run against a **real**
  NVDA 10-K fixture through the real parse→chunk→retrieve→chat pipeline, not just synthetic
  strings.
- **Integration — Redis** (`integration/test_rate_limit_redis.py`): the Redis-backed limiter
  against a real Redis, skipping if unreachable (mirrors the Postgres skip-offline pattern,
  ADR-0019); CI's `redis:7-alpine` service makes it run there.
- **Integration — SEC degradation** (`integration/test_sec_ingestion.py`): a simulated EDGAR
  outage degrades (dead-letter + `data_freshness` failed + run failed) instead of crashing —
  closes a gap where SEC ingestion never wrote `data_freshness` at all.

### Coverage gate (NFR-013)

`make coverage` runs the suite once under coverage and enforces two hard thresholds:

```
make coverage        # pytest --cov=app, then: fail-under 80 overall, fail-under 100 on finance+citation
```

CI runs the same as the backend `pytest` step. Local `make check` stays plain `pytest` so the dev
loop is fast.

## Frontend suites (`frontend/src/**/*.test.ts`, Vitest)

Pure-module tests, no DOM/React renderer (minimal toolchain): response validation accepts valid /
rejects malformed payloads (UI-001, `schemas.test.ts`); citation numbering first-appearance order
(CIT-006, `reportCitations.test.ts`); display formatting + unit conversion (`format.test.ts`); and
a source guard that fails the build if `dangerouslySetInnerHTML` is ever introduced (XSS,
`xssGuard.test.ts`). Run with `npm run test`.

## Evaluation harness (`backend/app/eval/`, spec §18)

Measures retrieval, answer, citation, hallucination, and abstention quality against the golden set
(`backend/tests/eval/golden_v0.jsonl`, 100+ questions built by `scripts/build_golden.py`). It
MEASURES the Phase 2c/3a pipeline — it never re-implements retrieval or verification.

- **Metrics** (`metrics.py`, unit-tested): Precision@K, Recall@K, MRR, NDCG (document-level vs
  `expected_sources`); numeric answer accuracy (Decimal, within tolerance); citation accuracy +
  hallucination (from the Phase 3a verifier's exposed labels); abstention correctness.
- **Judge** (`judge.py`): `LLMJudge` (versioned prompt `judge_v1`) for qualitative faithfulness,
  `FakeJudge` offline; `calibrate()` reports agreement vs human labels (target ≥ 0.85, §18.4).
- **Runner** (`runner.py`): drives each question through `chat.answer_question`, persists to
  `eval_runs`/`eval_results`. **A/B** (`ab.py`) diffs two configs per question. **Report-level**
  (`report.py`) and **feedback→golden triage** (`feedback.py`) round out §18.8/§18.9.
- **Gate / EVAL-002** (`gate.py`): fails a PR if Recall@5 drops > 2 pts, citation accuracy > 1 pt,
  or hallucination rises > 0.5 pts vs `app/eval/baseline.json`. Enforced in CI as a pytest
  integration test (`tests/integration/test_eval_runner.py`) that also proves a deliberate
  citation-accuracy regression is caught; the full set runs nightly via `scripts/run_eval.py`.

Only the deterministic metrics (numeric accuracy, abstention, citation accuracy, hallucination) are
meaningful in mock mode; Recall@K and judge faithfulness need live Voyage + an LLM key
(ADR-0009/0010/0020). The README benchmark table marks those _pending_.

## Tier 2 — E2E + accessibility (`e2e/`)

The §30.3 happy path: **search NVDA → load dashboard → generate report → ask question → receive
citation → open source**, plus an axe scan asserting no serious/critical WCAG 2 A/AA violations.

```
# with the stack running and seeded (API on :8000, frontend on :5173):
cd e2e && npm install && npm run install-browsers && npm test
```

Or run `e2e.yml` via "Run workflow". A full run needs a completed report + chat, which require an
LLM key (ADR-0006/ADR-0009) or the Fake-LLM seed.

## Tier 3 — Load (`load/locustfile.py`)

Drives the hot read endpoints (search, company, financials) and, with a token, authenticated chat,
to check the §8 latency targets. **Not yet run against a deployed stack** — the Tiingo free licence
blocks a public deploy until swapped (ADR-0007), and Phase 5d provides the hosted target.

```
uv run --with locust locust -f load/locustfile.py --host http://localhost:8000 \
    --users 50 --spawn-rate 5 --run-time 2m --headless
# set INVESTILENS_TOKEN=<bearer> to include the chat path
```

### NFR targets (§8) and results

| Metric | Target | p95 measured | Date / notes |
|--------|--------|--------------|--------------|
| `GET /companies/{ticker}` (cache hit) | < 150 ms (NFR-001) | _not yet run_ | needs deployed stack + Redis cache (Phase 5c/5d) |
| `GET /companies/{ticker}` (miss) | < 500 ms (NFR-001) | _not yet run_ | |
| `GET /companies/search` (cache) | < 300 ms (FR-001) | _not yet run_ | |
| retrieval (chat) | < 400 ms (NFR-002) | _not yet run_ | |
| chat first token | < 3 s (NFR-004) | _not yet run_ | needs LLM key |
| report generation | ≤ 90 s (NFR-003) | _not yet run_ | needs LLM key + worker (Phase 5d) |

Record each run here (replace _not yet run_ with the measured p95 + commit SHA + hardware) so the
NFR claims in the README benchmark table (§31) are backed by data, not assumed.
