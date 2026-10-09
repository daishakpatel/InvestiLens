# ADR-0024: Celery background jobs (Redis broker) and the Redis read-through cache

- **Status:** Accepted
- **Date:** 2026-10-08
- **Spec refs:** §25.1-3, JOB-001…006, CACHE-001…005

## Problem

Several phases stubbed "the Phase 5d worker": report generation only enqueued (ADR-0017), the
EDGAR poller was a pure function, alert CRUD had no dispatch, and the semantic/response cache was
never built. Phase 5d must make these real with a job system (separate queues, retries,
dead-letter, tracking, dedup, schedule) and a cache that never fails a request.

## Decision

- **Celery 5 with a Redis broker + result backend** (`celery[redis]`, new dep). Redis is already
  in the stack for rate limiting (ADR-0022), so no new infrastructure — one dependency covers the
  broker, results, cache, and limiter. (RabbitMQ would be a second piece of infra for no benefit
  at this scale.) Three queues (`interactive`/`ingestion`/`batch`, JOB-003) with per-queue worker
  concurrency; `acks_late` + `reject_on_worker_lost` + a visibility timeout for at-least-once
  redelivery (safe because tasks are idempotent, ING-001); uniform retry (exponential backoff +
  jitter, bounded attempts, JOB-001). Every task body runs inside `track_job` which owns the
  `jobs` row (running → done/failed with progress/stage, JOB-002); a failed row after exhausted
  retries is the dead-letter record. Beat holds the schedule in code, timezone America/New_York
  (JOB-006). Each task is a thin wrapper over an existing Phase 1-3 pipeline function — no new
  domain logic. A `background_jobs_enabled` seam keeps the API's enqueue behaviour identical to
  Phase 4a in tests/CI (no broker) and dispatches for real in a deploy.
- **A read-through Redis cache** (`app/cache`) behind one `get_or_load(family, key, loader)` entry
  point: versioned namespaced keys + per-family TTL (CACHE-001), single-flight lock against
  stampedes (CACHE-003), hit-rate counters per family wired into the existing `cache_hit_ratio`
  metric (CACHE-004), and invalidation on `filing.ingested` (CACHE-002). The cardinal rule is
  CACHE-005: **every** Redis operation is wrapped so any error falls back to the loader (the DB
  read) — a cache outage degrades to "always miss", never a failed request. Disabled by default
  (`cache_enabled`) so tests/CI hit the DB deterministically.
- **`minio` client** (new dep) implements the S3 `ObjectStorage` backend behind the existing
  interface (ADR-0012) — lighter than boto3 for a three-method put/get/exists and works against
  both MinIO (local) and AWS S3.

## Consequences

The job list (§25.2), the daily pipeline + pollers (§21.3), alert dispatch, retention purge, and
the nightly eval all run on a real, observable, retrying, idempotent worker fleet; report
generation finally progresses past `queued`. The cache cuts repeat DB reads for hot company data
without ever being able to take the site down. Costs: three new runtime deps (`celery`, `minio`,
and Redis's existing client) and the operational surface of a broker + workers + beat — mitigated
by the seams (`background_jobs_enabled`/`cache_enabled`/`rate_limit_backend`) that keep the test
suite broker-free and deterministic. Celery ships no type stubs, so `app.tasks.*` relaxes mypy's
untyped-decorator check (the task bodies stay fully annotated).
