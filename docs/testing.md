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
