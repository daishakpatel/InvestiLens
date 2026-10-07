# ADR-0019: Testing strategy, coverage gates, and CI tiers

- **Status:** Accepted
- **Date:** 2026-10-06
- **Spec refs:** §30 (testing strategy), §8 (NFR latency targets), NFR-013 (coverage), DR-004 (offline tests), SEC-007/AUTH-004 (IDOR), RAG-040 (injection)

## Problem

Phase 5a must make every layer verifiable in CI rather than by hand, across suites with very
different infrastructure needs: pure-logic unit/property tests run offline; integration and
migration tests need Postgres 16 + pgvector; the E2E happy path needs a browser plus a running
API+frontend; load tests need a load tool (k6/Locust) against a deployed stack with real data.
Running all of them on every push is slow and, for E2E/load, impossible in the default sandboxed
dev environment (no browsers, no load tooling, and the Tiingo free licence forbids public data
display per ADR-0007, so there is no live stack to load-test yet). We also had to choose between
adopting Testcontainers and keeping the existing throwaway-database fixture.

## Decision

Keep the existing session-scoped throwaway-DB fixture (`tests/integration/conftest.py`): it
creates/drops `investilens_test` on the configured server, runs real Alembic migrations against
real pgvector, and **skips** (not fails) when no server is reachable — so the unit suite stays
fully offline (DR-004) while CI's `pgvector/pgvector:pg16` service runs the integration/migration
tests. This already gives Testcontainers' isolation guarantee without a new dependency or a Docker
daemon inside the test process, so we do **not** adopt Testcontainers. Redis is not yet exercised
by any test (the cache/rate-limit paths are in-process seams; ADR-0018) so no Redis test service is
added until Phase 5c/5d wire a real backend. We organise CI into **tiers**: (1) `make check` — ruff
+ mypy + pytest (unit+integration+migration) + frontend lint/typecheck/vitest — runs on every PR
and is the merge gate, with a **coverage gate** enforced as a hard failure: 100% on `app/finance`
and `app/citation`, ≥80% overall (NFR-013). (2) A separate `e2e` workflow job installs Playwright +
axe and runs the search→dashboard→report→chat→citation→source happy path against an ephemeral
stack. (3) Load tests (Locust) and their NFR comparison live in `load/` and `docs/testing.md`, run
on demand against a deployed stack, with results recorded in the doc — not on every PR.

## Consequences

This keeps the per-PR gate fast and fully reproducible offline while still gating correctness,
security (injection corpus, IDOR), and resilience. The cost is that E2E and load are not green on
every commit: they are wired and runnable but gated behind infrastructure that only exists once a
stack is deployed (Phase 5d). We revisit adopting Testcontainers if we ever need per-test database
isolation or multiple concurrent DB versions, and we fold Redis into the test services the moment a
real cache/rate-limit backend lands.
