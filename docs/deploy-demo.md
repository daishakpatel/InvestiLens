# Deploying the public demo

The demo is the whole app in `DEMO_MODE`: fixture data for NVDA, AAPL and JPM, recorded AI
answers only, no registration, one shared sandbox account wiped nightly, and IP-keyed rate
limits. ADR-0050 has the reasons and the cost (about $30/mo). The blueprint is
[`render.yaml`](../render.yaml).

## First deploy (once, about 20 minutes)

1. In Render, choose **New → Blueprint**, pick this repository and the `main` branch. Render
   reads `render.yaml` and creates the database, Redis, the API, the worker and the static
   frontend. No secrets need entering: `JWT_SECRET` is generated, and the demo uses no model or
   data-provider keys.
2. Wait for the API's pre-deploy step. It migrates the database and seeds the fixtures
   (`scripts/seed_demo.py --if-empty --with-reports`, a few minutes on the first deploy and a
   no-op afterwards).
3. If Render gave the services different URLs from the ones in `render.yaml`, update
   `CORS_ALLOWED_ORIGINS` on the API and `VITE_API_BASE_URL` on the frontend, then redeploy.
4. Copy the API's **Deploy Hook** (Settings → Deploy Hook) into the GitHub repository secret
   `RENDER_DEPLOY_HOOK_URL`. Set the repository variable `DEMO_API_URL` to the API origin, for
   example `https://investilens-api.onrender.com`.
5. Check it: `DEMO_API_URL=<origin> scripts/smoke_demo.sh` prints
   `smoke: demo … is healthy, in demo mode, with registration closed`.

## Every later deploy

Merging to `main` deploys automatically. The `Deploy` workflow waits for CI to pass, triggers the
hook, then runs the smoke test. To deploy by hand from a laptop:

```bash
RENDER_DEPLOY_HOOK_URL=<hook> DEMO_API_URL=<origin> make deploy-demo
```

## Running the demo build locally

```bash
make demo-db                  # recreates and seeds assay_desk_demo, as the pre-deploy step does
scripts/vertical_slice.sh     # demo API on :8010 + production build on :5180, the Playwright
                              # five-minute path, then docs/media/demo.gif
```

`make record-demo` re-records the live-model answers the demo replays: guidance extraction,
the brief narrative and the guided question. It needs an LLM key and costs a few cents. Run it
after changing any prompt the demo uses. A stale recording isn't wrong; it's just not found, so
that answer falls back to "not enough evidence" until it's re-recorded.

## What to check after a deploy

- The banner reads "Demo: fixture data as of … Not investment advice." on every page.
- `/demo` opens all three scenarios.
- `POST /api/v1/auth/register` answers 403, and an oversized body answers 413.
- Logs show no `llm.call` with a live provider. The demo has no model key to use.

## Resetting by hand

The sandbox resets at midnight ET (`reset_demo_sandbox`). To reset now, run this on the worker:
`celery -A app.tasks.celery_app call reset_demo_sandbox`. To reseed the fixtures, empty the
companies table and redeploy, or run `python ../scripts/seed_demo.py --with-reports` on the API
shell.
