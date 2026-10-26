# ADR-0050: Public demo on one small Render stack, fixture data and recorded answers only

- **Status:** Accepted
- **Date:** 2026-10-25
- **Spec refs:** §36 (#23), Appendix H (NFR-ME-007 … NFR-ME-010)

## Problem

A reader should be able to try the app from a link, with no Docker, keys or database. A public
URL brings three risks:
- **Cost.** It runs every month.
- **Abuse.** Anyone can send it traffic.
- **Licensing.** Licensed prices must not be shown to the public (ADR-0007).

Hosting is already settled as Render (ADR-0023), but its blueprint ran five Starter services
(about $58/mo). `DEMO_MODE` existed as a flag that nothing read.

## Decision

`render.yaml` is now the demo blueprint, trimmed to the cheapest always-on shape:
- **Services:** one Starter API, one Starter worker serving all three queues with Beat
  in-process (`-B`), Postgres Basic-256MB, Redis Starter, and a static frontend. That is about
  **$30/mo** at 2026-10 list prices (docs/costs.md). The free tiers were rejected because of cold
  starts and the 90-day database expiry on a link meant to keep working.
- **Data:** `DEMO_MODE=true` serves fixtures only (`PROVIDER_MODE=mock`). The pre-deploy step
  seeds them with `scripts/seed_demo.py --if-empty`.
- **Model:** the LLM and embedder replay recorded or offline output whatever else is configured,
  so no model keys exist in the deployment.
- **Accounts:** registration answers 403. "Enter the demo" signs everyone into one shared
  sandbox account (`POST /auth/demo`), and a nightly Beat job deletes it with everything it owns.
- **Abuse controls:** rate limits are forced on and keyed by client IP, since every visitor
  shares one account. Request bodies over 256 KiB are refused (413), as are bodies of unknown
  length (411). The existing per-question length cap still applies.
- **Banner:** `GET /meta/demo` feeds the line "Demo: fixture data as of {date}. Not investment
  advice."
- **Deploy and smoke test:** `make deploy-demo` triggers the deploy hook. `scripts/smoke_demo.sh`
  then checks health, that demo mode is on, and that registration is closed. CI runs the same
  check after each deploy.

## Consequences

The demo costs about $30 a month and can't spend on a model or show licensed data. A visitor can
change nothing that outlives the night. What the visitor sees is limited:
- A chat question with no recorded answer gets the honest "not enough evidence" reply. The
  demo is good for the guided paths and weak for open-ended questions.
- The API and frontend are on different `onrender.com` subdomains (a public suffix), so the
  SameSite=Strict refresh cookie isn't sent cross-site. A page reload ends the demo session, and
  the visitor clicks "Enter the demo" again.

Revisit if traffic outgrows one worker, if a custom domain puts both on one site, or if a model
budget for live answers is approved.
