# ADR-0017: Research job orchestration and idempotency single-flight

- **Status:** Accepted
- **Date:** 2026-10-02
- **Spec refs:** §24.2, §25.1, API-003, JOB-005

## Problem

`POST /research` must follow the async job pattern (202 + `job_id`/`research_id`, progress via
polling/SSE) and single-flight duplicate concurrent requests for the same company so a user
mashing the button does not spawn N expensive report generations (JOB-005, API-003
`Idempotency-Key`). But the Celery worker that actually runs generation is Phase 5d, and live
generation needs an LLM key (ADR-0009) that is absent offline.

## Decision

`POST /research` **enqueues** rather than runs: it creates a pending `research_reports` row and a
`jobs` row (`job_type="research_report"`, `status="queued"`, `result_ref` = the report id,
`params` = `{ticker, data_version_key, idempotency_key, force_refresh}`), and returns 202. Actual
execution (calling `app.research.report.generate_report_for_ticker`) is wired to the Phase 5d
worker; until then the job stays `queued` and the report stays `pending`. Single-flight resolves
in order: (1) if an `Idempotency-Key` header matches a prior job's `params.idempotency_key`,
attach to it; (2) else if a non-terminal (`queued`/`running`) job exists for the same company,
attach to it; (3) else create a new job. `GET /research/jobs/{job_id}` maps the `jobs` row to
`JobState`; `/events` emits that state as a single SSE frame; `GET /research/{research_id}` and
`/companies/{ticker}/research/latest` read persisted reports (Phase 3b) and return an
empty-but-valid report envelope while a job is still `queued`.

## Consequences

The contract-level behaviour (202, polling, SSE, single-flight) is real and testable now with no
LLM key and no worker, and no duplicate generations are triggered. The cost is that an enqueued
report does not progress to `complete` until the Phase 5d worker lands; the endpoints surface this
honestly (`queued`/`pending`) rather than faking a finished report. The single-flight window is
"any non-terminal job for the company", which is intentionally coarse until `data_version` can be
computed cheaply before generation; revisit when the worker computes and persists `data_version`
up front.
