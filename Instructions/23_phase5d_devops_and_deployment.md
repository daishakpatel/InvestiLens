# Phase 5d — DevOps, Background Jobs & Deployment

**Prerequisites:** the system should be functionally complete (Phase 1–4) and ideally
Phase 5a–5c done first, since you want tests, observability, and security in place before
shipping.
**Blocks:** nothing — this is the last MVP phase before Phase 6's advanced features.
**Full spec sections:** §25 (background jobs, scheduling, caching, rate limiting), §31
(DevOps & deployment).

## Objective

Formalize the background job system (some of it was stubbed in earlier phases), wire up
caching and rate limiting for real, containerize everything, set up CI/CD, and deploy a live
demo.

## Scope

### Background jobs (formalizing what earlier phases stubbed)

1. **Celery queues:** separate `interactive` (user-triggered, e.g. report generation),
   `ingestion`, and `batch` queues with independent worker concurrency.
2. **Job list:** confirm all of these exist and are scheduled correctly: `fetch_sec_filings`,
   `fetch_market_data`, `fetch_news`, `fetch_insider_and_holdings` (if Phase 6 data exists),
   `parse_documents`, `generate_embeddings`, `update_financial_metrics`,
   `generate_research_report`, `refresh_company_data`, `poll_edgar_new_filings`,
   `send_alerts`, `run_eval_suite`.
3. **Job reliability (JOB-001…006):** idempotent, exponential backoff + jitter retries, max
   attempts, dead-letter queue, job tracking with progress/stage events in the `jobs` table,
   visibility timeouts, graceful shutdown, single-flight deduplication (confirm the
   `POST /research` single-flight behavior from Phase 4a is actually backed by a real Celery
   mechanism, not just an API-layer check).
4. **Scheduled pipeline (Celery Beat):** daily 02:00 ET SEC → market → news → processing →
   embeddings pipeline; EDGAR poller at ≤ 10 min intervals for watched companies; news poller
   at ~15 min; price refresh EOD.
5. **Alert dispatch:** this is the piece Phase 4b's alert CRUD was waiting on — actually check
   for new filings/price moves/news matching each `alerts` row and send notifications
   (email + in-app) within 30 minutes of the triggering event.

### Caching & rate limiting

6. **Redis caching:** company metadata, stock prices, financial metrics, popular research
   reports, FAQ/semantic chat cache — with per-type TTLs, versioned keys, invalidation on
   `filing.ingested`/`metrics.updated` events, stampede protection (single-flight lock), and a
   safe fallback to the database if Redis is down.
7. **Rate limiting:** 100 req/min/user general, 20 AI requests/hour/user, `429` with
   `Retry-After`; per-user monthly AI budget enforcement (ties into Phase 4b's
   `ai_budget_month_usd`) with a global circuit breaker on total LLM spend.

### DevOps

8. **`docker-compose.yml`:** api, worker (per queue), beat, postgres+pgvector, redis, minio,
   frontend dev server, optional grafana/prometheus — `make up` gets a fresh clone running.
9. **CI/CD (GitHub Actions):** lint → type-check → unit tests → integration tests → build →
   security scans → eval smoke gate (Phase 5b) → E2E on preview → deploy on merge to main.
   Branch protection requiring these checks.
10. **Production deployment:** frontend on Vercel/CloudFront, API on a PaaS (Render/Railway) or
    ECS, managed Postgres with pgvector, managed Redis. Document the choice in an ADR if not
    already covered by Phase 0a.
11. **Backups:** automated daily DB backups with a documented, *tested* restore procedure; raw
    documents in versioned object storage.
12. **Hosted demo mode:** pre-generated reports for the seed tickers, read-only for anonymous
    visitors, a low/zero AI quota to control cost — this is the link you'll actually put on
    your resume.
13. **Cost documentation (`docs/costs.md`):** rough monthly cost estimate for hosting +
    provider APIs + LLM usage at demo-scale traffic.
14. **`make seed` / `make eval`:** confirm these Makefile targets exist and work from a clean
    clone within the 15-minute target.

## Out of scope for this file

No new product features. If something here reveals a missing piece from an earlier phase (e.g.
alert dispatch has nowhere to actually check filings because that logic doesn't exist yet), go
fix the smallest thing needed rather than redesigning.

## Definition of Done

- [ ] Fresh clone → `make up` → `make seed` → running dashboard in under 15 minutes
- [ ] All scheduled jobs run on their intervals and are idempotent under simulated retry
- [ ] Alert dispatch actually sends a notification within 30 minutes of a simulated triggering
      event (e.g. a test filing ingestion)
- [ ] Redis down doesn't break requests — falls back to DB, verified by a test
- [ ] Rate limits and AI budgets are enforced with correct `429`/budget-exceeded responses
- [ ] CI/CD pipeline runs end-to-end and deploys to staging automatically on merge
- [ ] A hosted demo is live with pre-generated seed-company reports and a documented,
      restrictive AI quota
- [ ] A backup restore has actually been tested once, not just configured
- [ ] `docs/costs.md` has a real, itemized estimate
