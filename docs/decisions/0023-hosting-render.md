# ADR-0023: Hosting on Render (API + workers + managed Postgres/Redis), frontend static

- **Status:** Accepted
- **Date:** 2026-10-08
- **Spec refs:** §31.3, NFR-012, Appendix F #6

## Problem

Phase 5d needs a concrete production target to write the deploy config, CI deploy step, and cost
estimate against (§31.3 says "portfolio-sized; don't over-engineer"). The app is a modular
monolith (ADR-0001) plus Celery workers and a Beat scheduler, needing managed Postgres+pgvector
and managed Redis. The choice drives `render.yaml`, `docs/costs.md`, and the CI deploy workflow.

## Decision

Deploy to **Render** via an in-repo Blueprint (`render.yaml`): a Docker **web service** for the
API, three Docker **worker services** (one per Celery queue — `interactive`/`ingestion`/`batch`),
a Docker **worker** for Beat, a managed **Postgres 16** database (pgvector ships with it), and a
managed **Redis** (broker + result backend + cache + rate-limit store). The **frontend** deploys
as a Render **static site** (`npm run build` → `frontend/dist`), with Vercel noted as an equally
valid alternative (the SPA is platform-agnostic; it only needs `VITE_API_BASE_URL`). Migrations
run as a deploy step via the API service's `preDeployCommand: alembic upgrade head` (§31.2).
Render was chosen over Railway/Fly.io for the simplest fit: Blueprint-as-code covering DB + Redis
+ multiple services in one file, native Docker + background-worker + cron support, and a free/low
tier adequate for a demo. The user confirmed Render.

## Consequences

One `render.yaml` describes the whole topology, so the deploy is reproducible and reviewable, and
CI can gate it (deploy only on green, ADR via `deploy.yml`). The cost is single-platform lock-in
and Render's cold-start/plan limits on the free tier — acceptable for a portfolio demo and easily
re-pointed (the images and blueprint are standard Docker). **The actual live deploy is not done
from this environment** (no Render account/secrets here, and ADR-0007's Tiingo license blocks
showing price data publicly — the demo runs `PROVIDER_MODE=mock` for prices to stay compliant);
the blueprint, workflow, and cost doc are built and validated, and a human runs the one-time
Blueprint sync.
