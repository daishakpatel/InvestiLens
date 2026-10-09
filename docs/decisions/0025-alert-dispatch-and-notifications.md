# ADR-0025: Alert dispatch and notification delivery

- **Status:** Accepted
- **Date:** 2026-10-08
- **Spec refs:** §26.2, SEC-014, Phase 5d scope #5

## Problem

Phase 4b shipped alert-rule CRUD (`alerts` table) but nothing evaluated the rules or delivered
anything — the dispatch side was explicitly "waiting on Phase 5d". The DoD requires a notification
delivered within 30 minutes of a triggering event (new filing / price move / matching news), via
email + in-app. No email provider is configured in this project.

## Decision

- **`notifications` table + `app/alerts/dispatch.py`.** The `send_alerts` Beat task (every 5 min)
  evaluates each active alert against a watermark (`last_triggered_at`): a new filing of the
  alert's type, a latest daily price move past a threshold, or new news in a category, all keyed
  off *ingestion* time so the 30-min SLA is measured from when InvestiLens learns of the event
  (EDGAR poll ≤10 min + dispatch ≤5 min stays well inside 30). Firing an alert writes a
  `notifications` row and advances the watermark, so re-evaluation without a new event sends
  nothing (idempotent, JOB-001).
- **Delivery behind a `NotificationSender`.** Every notification is persisted in-app (durable,
  read via `GET /notifications`). For the `email` channel it is *also* sent through a pluggable
  `EmailBackend`: `LogEmailBackend` by default (no SMTP provider configured — delivery is logged
  PII-safe rather than silently dropped), or `SmtpEmailBackend` when `SMTP_*` is set. Keeping
  email behind the interface means dispatch never knows which backend is live and tests use the
  log backend with zero network.

## Consequences

The alert feature is now end-to-end: a rule created via the Phase 4b API produces a real,
readable notification on the next triggering event, verified by an integration test that ingests
a test filing and asserts a notification lands. The cost: a new table (one migration) and the fact
that real email is unproven until an SMTP provider is configured — acceptable, since the in-app
record is the durable channel and email is additive. The `notifications` row is `ON DELETE SET
NULL` on alert/company so it outlives the rule, and cascades with the user account (SEC-014).
