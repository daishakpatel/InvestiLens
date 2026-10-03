# ADR-0018: Rate-limit middleware seam

- **Status:** Accepted
- **Date:** 2026-10-02
- **Spec refs:** §24.1, §25.4, NFR-009

## Problem

Phase 4a must put the rate-limiting *layer* in place (§24.1) so later work has a single call site,
but the real limits, per-route tiers, and the shared store (Redis) are Phase 5c (§25.4). We need
the seam without shipping a distributed limiter or anything that makes the test suite flaky.

## Decision

A single `RateLimitMiddleware` (`app/api/middleware.py`) sits in the app stack. It is **disabled by
default** (`rate_limit_enabled=False`) and, when enabled, applies an in-process token bucket keyed
by client host at `rate_limit_per_minute` (default 120), returning an RFC 7807 `429` through the
shared problem handler on exhaustion. The in-process store is explicitly a stand-in; Phase 5c
swaps the bucket backend for Redis and configures per-route limits behind the same middleware
without touching routers.

## Consequences

The limiter exists as one well-defined seam with a correct 429 problem response, and tests stay
deterministic because it is off by default and never shares state across workers. The cost is that
the in-process bucket does not coordinate across processes, so it is not a real limit until the
Redis backend lands — enabling it in a multi-worker deployment before Phase 5c would under-count.
Revisit when §25.4 configures production limits.
