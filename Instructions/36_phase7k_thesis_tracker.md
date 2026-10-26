# Phase 7k — Investment Thesis Tracker (User Thesis, Evidence Linking, Trigger Alerts)

**Prerequisites:** 7a (alert registry), Phase 4b (auth), Phase 6a (portfolio/watchlist). 7e and 7j
recommended: they provide evidence and the briefs to link to.
**Blocks:** 7l (demo flow).
**Full spec sections:** §26.2 (alerts), §17 (report schema), §14 (retrieval). Requirement IDs:
`FR-TH-001` … `FR-TH-014`, `SEC-TH-001` … `SEC-TH-003`, `AGT-TH-001`.

## Objective

Let an analyst write down *why* they own or follow a company, in the form of a falsifiable
thesis with explicit **KPIs and triggers**, and have the app keep score as new data arrives.
This is the one place the app should feel like a working notebook rather than a reference
library. It also shows engineering depth for the project: a user-owned data model, private by
construction, with deterministic evaluation and no AI involvement in verdicts.

**Design rule.** The app records and checks what the user said. It never tells the user what to
believe or do. The thesis is the user's text. KPI evaluation is arithmetic against stored
metrics. AI, if used at all, only helps *draft* a thesis from the user's own input, always
labelled as a suggestion the user must accept.

## Scope

### 1. Data model

1. Tables:
   - `theses(id, user_id, company_id, title, body_md, stance, status, created_at, updated_at)`
     with `stance` ∈ `long | short | watch | avoid` (descriptive tag chosen by the user, not
     advice from the app) and `status` ∈ `active | closed`.
   - `thesis_kpis(id, thesis_id, metric, comparator, threshold, unit, period_type, label,
     rationale, created_at)`: a measurable claim. `comparator` ∈ `gte | lte | gt | lt`. The
     `metric` must be one of a registry of trackable metrics (derived from `financial_metrics`,
     7b quarterly/TTM, 7d scores, 7h multiples, 7i guidance outcome) — validated at write.
   - `thesis_events(id, thesis_id, kind, occurred_at, ref_type, ref_id, note)` — append-only log:
     `kpi_met`, `kpi_broken`, `red_flag`, `brief_published`, `user_note`, `status_changed`.
   - `thesis_revisions(thesis_id, revision, body_md, created_at)` — keep history; edits never
     overwrite.
2. Ownership: every row is owned by `user_id`. All queries filter by the authenticated user;
   other users' theses return 404. Add an isolation test for each endpoint (`SEC-TH-001`).
3. Limits: 20 active theses per user, 10 KPIs per thesis, `body_md` ≤ 20,000 characters.

### 2. KPI evaluation (deterministic)

4. `thesis/evaluator.py`: for each active KPI, fetch the latest value for the metric/period from
   the backend (same selection rules as the rest of the app), compare with the threshold using
   Decimal, and emit a state: `met | broken | no_data`. Persist the current state on the KPI
   and append a `thesis_events` row **only on transitions** (not every run).
5. Units: the KPI threshold unit must match the metric's canonical unit (ratios as decimals).
   The form shows the metric's unit and converts percent input to a decimal; the API rejects a
   threshold that looks like a unit mistake (e.g. a margin threshold >5.0 on a ratio metric) with
   a clear message.
6. A KPI on a metric with `not_applicable` status (bank + gross margin) is rejected at creation.
7. Evaluate: after `update_financial_metrics` completes for a ticker (add a Celery task hook),
   and when a new red flag (7e) or brief (7j) is created for a company. Do not poll.
8. Event-driven links: when a red flag is created for a thesis's company, append a `red_flag`
   event referencing it. When a brief is published, append `brief_published`. These are
   **informational**; they do not change KPI state.

### 3. Alerts

9. Register `thesis_trigger` (7a). Fires on KPI transitions into `broken` (and optionally
   `met`, per param `notify_on`). `event_key = thesis_kpi:{kpi_id}:{state}:{period_end}`
   so a flapping value does not spam; the same state for the same period fires once.
   Body: "Your KPI '{label}' ({metric} {comparator} {threshold}) is now {state}: latest
   {value} ({source_id})." Quote only the user's own label and thresholds plus the cited value.

### 4. Optional AI assistance (user-initiated, labelled)

10. "Draft from my notes": the user pastes rough notes; the model returns a structured *suggested*
    thesis (title, 3–5 candidate KPIs chosen **only from the metric registry**, each with a
    suggested threshold the user must edit). The response schema forbids freeform metrics.
    The UI shows suggestions in a diff-like review list; nothing is saved until accepted. No
    stance is suggested.
11. User notes are input data, not instructions (prompt-injection test). Do not send other users'
    data. Log token counts only, never thesis text (`SEC-TH-002`: thesis bodies are private;
    exclude them from logs, metrics labels and error reports).
12. A hard rule: no AI-generated sentence ever says whether the thesis is "right", "wrong",
    "playing out" or "at risk". Verdict language is limited to KPI states (met/broken/no data).

### 5. API

13. Standard CRUD: `GET/POST /theses`, `GET/PATCH/DELETE /theses/{id}`, `POST /theses/{id}/kpis`,
    `PATCH/DELETE /theses/{id}/kpis/{kpi_id}`, `GET /theses/{id}/events?limit=`,
    `GET /theses/{id}/revisions`, `POST /theses/draft` (AI assist; rate-limited).
    `GET /thesis/metric-registry` lists trackable metrics with unit and applicability. All
    additive; update docs and openapi.
14. Deleting a thesis hard-deletes its KPIs, events and revisions (user data deletion;
    consistent with the retention/purge policy `SEC-014`). Document it. Include theses in the
    "delete my account" path if one exists.

### 6. UI

15. A "Thesis" tab on the company page and a "Theses" index page: thesis text (markdown rendered
    safely: sanitise HTML), KPI table with state chips (text + icon; `met`/`broken` do **not**
    use green/red since those mean gain/loss — use neutral and `warning` tokens), latest value,
    threshold, and a sparkline from stored history. Timeline of events below it, each linking to
    the flag, brief or metric evidence.
16. Editing creates a revision; a "History" drawer shows revisions with simple diffs (reuse the
    word-diff component from the filing diff view).
17. Empty states explain how to start. The draft-assist button states that it only suggests
    metrics and thresholds, and that the user decides.
18. Markdown rendering is sanitised (no raw HTML, no remote images) with an XSS test.

## Out of scope

Position sizing, P&L tracking, price targets, sharing or collaborating on theses, social
features, AI judgement of thesis quality, backtesting a thesis, and importing from brokerages.

## Docs to update in the same PR

`docs/database.md`, `docs/api.md`/`openapi.json`, `docs/ui.md`, security notes (private user
text, log exclusion), prompt registry (`thesis_draft_v1`), spec Appendix H, ADR-0049 (events only
on transitions; user text excluded from logs; no AI verdicts).

## Definition of Done

- [x] User A cannot read, edit, delete or list user B's theses, KPIs, events or revisions (404 on
      every endpoint, tested)
- [x] KPI creation rejects unknown metrics, `not_applicable` metrics, and unit-mistake
      thresholds with clear errors
- [x] Evaluator marks `met`/`broken`/`no_data` correctly with Decimal comparisons (boundary case
      `gte` equal → met)
- [x] Events are appended only on state transitions; running the evaluator twice adds nothing
- [x] `thesis_trigger` fires once per `(kpi, state, period_end)` and its text contains only the
      user's label/threshold and the cited value (advice test)
- [x] Red-flag and brief events appear in the timeline and do not change KPI state
- [x] Editing a thesis creates a revision; history shows diffs; deleting hard-deletes all child
      rows
- [x] AI draft: output restricted to registry metrics; suggestions unsaved until accepted;
      injection test passes; no stance suggested
- [x] Thesis text is absent from application logs and Prometheus labels (log-capture test)
- [x] Markdown is sanitised (XSS test) and verdict colours avoid green/red
- [x] Playwright: create a thesis, add a KPI, simulate the metric crossing the threshold, see
      the timeline event and the in-app notification
- [x] Docs and ADR-0049 written; `make check` and `make openapi` clean
