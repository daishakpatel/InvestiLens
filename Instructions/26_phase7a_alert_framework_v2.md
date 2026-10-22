# Phase 7a — Alert Framework v2 (Per-User Rules, Watermarks, Event Types)

**Prerequisites:** Phase 5d (alert dispatch, `send_alerts` Beat task, notification sender) and
Phase 4b (auth/users) done. Phase 6b done if you want the existing "new risk factor" alert type
migrated (it should be).
**Blocks:** 7e (red-flag alerts), 7i (guidance-miss alert), 7j (brief-ready notification), 7k
(thesis-trigger alert). Do this file first in Phase 7: four later files register event types
here instead of each hand-rolling dispatch logic.
**Full spec sections:** §26.2 (alert dispatch), §37.4 (new-risk alert). Requirement IDs for this
file: `FR-AL-001` … `FR-AL-012`. Add them to a new **Appendix H** in the spec as you go.

## Objective

Make alerts a framework instead of a single hard-coded check. Today `alerts/dispatch.py` fires
on a small fixed set of conditions, the user cannot configure anything (see `TODO.md`: "alert
config missing"), and a newly created alert can replay old events. Phase 7 adds five new event
types, so before adding them, fix the foundation: one registry of event types, per-user rules
with thresholds, and a per-alert watermark so an alert only ever fires on events that happened
*after* it was created.

## Why this file exists (the problem, concretely)

1. **Replay bug.** An alert created today can fire on an 8-K filed last month because dispatch
   compares against "events since the last send," and a new alert has no last send. A user who
   sets up an alert and instantly receives six stale notifications will distrust every later one.
2. **No configuration.** Users cannot choose *which* event types, *which* tickers, or a
   *threshold* (e.g. "price move > 5%"). The `Alert` model exists but the UI/API only create a
   fixed shape.
3. **Every new event type would copy-paste.** Phase 7 adds red flags, guidance misses, brief
   readiness and thesis triggers. Without a registry each would add its own query, its own
   dedupe, and its own bugs.

## Scope

### 1. Event-type registry (`backend/app/alerts/registry.py`, new)

1. Define `AlertEventType` as a frozen dataclass: `key` (stable string, e.g. `new_filing`,
   `price_move`, `new_risk_factor`, `red_flag`, `guidance_miss`, `brief_ready`,
   `thesis_trigger`), `label`, `description`, `params_schema` (a Pydantic model for the
   user-configurable threshold, may be empty), `detector` (callable, below), `default_enabled`.
2. A `detector` is a pure-ish function `(session, alert, since: datetime, until: datetime) ->
   list[DetectedEvent]`. `DetectedEvent` carries: `event_key` (a deterministic string that is
   identical if the same real-world event is detected twice, e.g.
   `red_flag:NVDA:0000320193-24-000123:item_4.02`), `occurred_at` (UTC), `company_id`,
   `title`, `body` (plain text, no advice language), `source_ids` (list of backend-issued IDs
   such as the filing's `Document` source ID), and `severity` (`info|warning|critical`).
3. Register the existing detectors (new filing, price move, new risk factor) through the
   registry unchanged in behavior. Later Phase 7 files call `register(...)` at import time.
4. Unknown `event_type` values already stored on old `Alert` rows must not crash dispatch: log
   a warning with the alert id and skip.

### 2. Per-alert watermark (fixes the replay bug)

5. Add `Alert.watermark_at TIMESTAMPTZ NOT NULL` (migration; backfill existing rows with
   `now()` at migration time, **not** with their `created_at`, so deploying does not suddenly
   replay history either). New alerts set `watermark_at = created_at`.
6. Dispatch for an alert considers only events with `occurred_at > watermark_at` and
   `occurred_at <= run_started_at`. After the run succeeds for that alert, set
   `watermark_at = run_started_at` (the run's start, **not** `now()` at finish, so events that
   land mid-run are picked up next time rather than lost).
7. Idempotency does not rely on the watermark alone. Add a unique constraint on
   `Notification(alert_id, event_key)`. Insert with `ON CONFLICT DO NOTHING`. Two overlapping
   Celery runs, or a crash between "notification inserted" and "watermark advanced," must not
   double-send. (Email/push send happens only for rows the insert actually created.)
8. If the watermark advance fails after notifications were created, the next run re-detects
   the same events and the unique constraint swallows them. Test this explicitly.

### 3. Per-user alert rules API + model

9. Extend `Alert` with `event_type` (string, validated against the registry), `params`
   (JSONB, validated against the type's `params_schema`), `company_id` (nullable; null means
   "every ticker on my watchlist"), `channels` (subset of `in_app`, `email`), and `enabled`.
10. Endpoints (additive, so no ADR; update `docs/api.md` and run `make openapi`):
    - `GET /alerts/event-types` → registry contents so the UI can render the form with no
      hard-coded list.
    - `POST /alerts`, `PATCH /alerts/{id}`, `DELETE /alerts/{id}`, `GET /alerts`.
    - Validation errors return the existing error envelope with field-level detail.
11. Scoping: a user can only see and edit their own alerts (reuse the existing ownership
    check pattern from watchlist). A "watchlist-wide" alert evaluates against the user's
    watchlist at run time, not at creation time, so adding a ticker later is covered.
12. Limits: max 50 alerts per user (config value). Exceeding it returns 422 with a clear
    message. This protects the 5-minute dispatch loop from a pathological account.

### 4. Dispatch loop hardening

13. One failing alert must not block the others. Wrap each alert's evaluation in its own
    try/except, log `alert_id`, `event_type`, and exception class, increment a Prometheus
    counter `alert_dispatch_errors_total{event_type}`, and continue.
14. Add counters `alerts_fired_total{event_type,channel}` and a histogram
    `alert_dispatch_latency_seconds` (event `occurred_at` to notification created). The Phase 5d
    DoD says alerts must send within 30 minutes; this makes that measurable instead of
    claimed. Add the panel to the existing Grafana dashboard JSON.
15. Batch window: if one alert detects more than 20 events in one run (e.g. a new alert on a
    company with many filings after a long outage), collapse into a single digest notification
    ("12 new filings for NVDA") instead of 12 separate ones. The digest still lists each
    `event_key` in `Notification.payload` so nothing is hidden.

### 5. Frontend

16. Replace the fixed `AlertsButton` flow with an "Alerts" settings panel: list of rules,
    toggle, delete, and a "New alert" form generated from `GET /alerts/event-types`
    (`params_schema` → typed inputs via Zod, no hand-written form per type).
17. Empty and error states are explicit. A rule whose event type no longer exists shows a
    "no longer supported" badge, never disappears silently.
18. Notification items link to the underlying evidence (filing, brief, red-flag row) using the
    `source_ids` from the event. The notification text never contains investment advice
    (reuse `citation.advice.contains_advice` in a unit test over every registered detector's
    sample output).

## Out of scope

Push notifications, SMS, Slack/webhook channels, per-alert quiet hours, and snooze. Do not
build a generic rules engine or expression language; each event type has a typed params model.
Do not change the email provider or template styling beyond adding the event title/body.

## Docs to update in the same PR

`docs/database.md` (Alert columns, Notification unique constraint), `docs/api.md` +
`docs/openapi.json`, `docs/architecture.md` (one paragraph on the registry), Appendix H in the
spec, and an ADR (next number after 0038, i.e. 0039) recording: "watermark per alert +
unique `(alert_id, event_key)` as the idempotency mechanism".

## Definition of Done

- [x] Creating an alert on a ticker that has older matching events fires **zero**
      notifications on its first run (regression test with a seeded old filing)
- [x] An event occurring after creation fires exactly once, even if dispatch runs twice
      concurrently (test with two sessions) and even if the watermark update is made to fail
- [x] `Notification(alert_id, event_key)` unique constraint exists and is exercised by a test
- [x] Migration backfills `watermark_at = now()` for existing rows; downgrade works
- [x] Event-type registry holds the three legacy detectors, and `GET /alerts/event-types`
      returns them with JSON-Schema-derived param definitions
- [x] Invalid params for an event type are rejected with a field-level 422
- [x] A detector raising an exception does not stop other alerts in the same run (test), and
      `alert_dispatch_errors_total` increments
- [x] More than 20 events in one run collapse into one digest that still lists every
      `event_key`
- [x] Per-user isolation: user B cannot read, edit or delete user A's alerts (404, not 403)
- [x] Alerts settings UI creates, toggles and deletes a rule against the mock API in a
      Playwright test
- [x] Every registered detector's sample output passes `contains_advice == False`
- [x] The alert-latency histogram is populated by the Phase 5d simulated-filing test, and the
      Grafana panel exists
- [x] Docs, Appendix H and ADR-0039 written; `make check` and `make openapi` clean
