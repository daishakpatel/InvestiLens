# ADR-0022: Redis-backed rate limiting and per-user AI budget enforcement

- **Status:** Accepted
- **Date:** 2026-10-07
- **Spec refs:** §25.4, §29 (SEC-008), NFR-008, NFR-009

## Problem

ADR-0018 deliberately left the real limiter backend and per-user AI budget enforcement for
"Phase 5c (§25.4)". Three separate deferred-items notes (Phase 4a, 4b, this phase) point here.
The task file for this phase doesn't enumerate exact numbers (requests/minute, AI requests/hour,
default budget) — the spec gives *example* numbers (§25.4: "100 requests/minute/user", "20 AI
requests/hour/user") which we adopt directly rather than inventing new ones.

## Decision

- **Rate limiting:** `RateLimitMiddleware` (`app/api/middleware.py`) gains a Redis-backed fixed
  window counter (`INCR` + `EXPIRE`, one round trip, no Lua needed at this scale) used when
  `rate_limit_backend="redis"` (new setting; default stays `"memory"` so existing tests/CI remain
  deterministic and infra-free, per ADR-0018 and ADR-0019). Two tiers: `rate_limit_per_minute=100`
  (general, matches the spec's example) keyed by user id (falling back to client host for
  anonymous reads), and `rate_limit_ai_per_hour=20` applied specifically to `/chat*` and
  `/research` (the AI-cost endpoints). Both return RFC 7807 `429` with `Retry-After`.
- **AI budget:** `users.ai_budget_month_usd` (already in the schema, unused) gets a default at
  registration (`default_ai_budget_month_usd=Decimal("5.00")`, configurable). A new
  `app/billing/budget.py` sums `llm_calls.cost_usd` for the user's current calendar month
  (attributing calls to a user needs a new `llm_calls.user_id` column — migration in this phase)
  and raises `BudgetExceededError` (→ RFC 7807 `402`) before the LLM-cost-incurring path in
  `POST /chat` (qualitative synthesis only; deterministic metric answers are free) and
  `POST /research`. A global daily-spend gauge feeds the `llm_spend_over_budget` alert (OBS-003)
  as a circuit breaker signal; it does not itself block requests (a single user's cap already
  bounds the worst case) to avoid a cross-tenant outage from one heavy user.
- **Testing:** the Redis-backed limiter is unit-tested against `fakeredis` (new dev dep — an
  in-memory drop-in with the same wire protocol, avoiding a live Redis in unit tests while still
  exercising real `INCR`/`EXPIRE`/`TTL` semantics) and has one integration test against a real
  Redis that skips if `REDIS_URL` is unreachable, mirroring the existing skip-offline pattern for
  Postgres (ADR-0019).

## Consequences

Rate limits and AI spend are now enforced for real when `rate_limit_backend="redis"` is set (a
one-line config change for deployment — no router changes), closing the gap ADR-0018 left open.
The in-process backend remains the test/CI default, so no existing test becomes flaky. Cost:
limiter state still doesn't survive a Redis restart (acceptable — it's abuse protection, not
durable accounting; durable accounting is `llm_calls`, which is already persisted).
