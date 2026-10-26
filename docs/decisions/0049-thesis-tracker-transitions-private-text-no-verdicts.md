# ADR-0049: Thesis tracker: events only on data transitions, user text kept out of logs, no AI verdicts

- **Status:** Accepted
- **Date:** 2026-10-25
- **Spec refs:** §26.2, Appendix H (FR-TH-001 … FR-TH-018, SEC-TH-001 … SEC-TH-003, AGT-TH-001)

## Problem

Users write down why they follow a company, with measurable KPIs, and want the app to keep score
as new data arrives. This is the first user-authored, private free text in the app, and the
first place where the app could seem to judge an investment view. Four things had to be settled:
- **Timeline noise.** What counts as a timeline event, so it is not flooded by every evaluation
  run or by the user's own edits?
- **Privacy.** How private text stays out of logs, metrics and other users' views.
- **The model's role.** How much an optional AI helper may do.
- **Fixing the inputs.** How a KPI's metric and unit are fixed so that evaluation stays plain
  arithmetic.

## Decision

**Data and ownership.**
- Four tables: `theses`, `thesis_kpis` (current state on the row), an append-only
  `thesis_events` and `thesis_revisions`.
- Everything hangs off `theses.user_id` with `ON DELETE CASCADE`, so deleting a thesis, or the
  account (the existing hard-delete path), removes all of it.
- Every API lookup is scoped to the signed-in user; another user's row answers 404, never 403.

**KPIs come from a curated registry** (`app/thesis/registry.py`, `thesis_metric_registry_v1`).
- It covers stored `financial_metrics` rows (FY/Q/TTM, 7d scores, 7h multiples at the latest
  close), quarterly margins computed as 7i does, revenue YoY growth, and revenue against the 7i
  guided midpoint.
- Each entry has one canonical unit, with ratios as decimals.
- A KPI is rejected at write when:
  - the metric is unknown or not in the registry;
  - the period does not exist for that metric;
  - the metric is not applicable to the sector (a bank's gross margin);
  - the threshold looks like a unit mistake (a ratio beyond ±5, or a score outside its range).
- The form takes a ratio as a percent and stores the decimal with exact string arithmetic.

**Evaluation is Decimal arithmetic against the latest stored value**, giving `met`, `broken` or
`no_data`.
- An event is appended only when the state changes because the data changed.
- The first evaluation, and the one after the user edits the metric, period, comparator or
  threshold, is a **baseline** with no event: the user just set it, so it is not news.
- Moving into `no_data` updates the KPI without an event, so re-running the evaluator adds
  nothing.
- Evaluation runs from one idempotent hook, `refresh_company_theses`, called after metrics are
  rebuilt, after a red-flag scan, after a brief is stored, and on a KPI write. Nothing polls.
- The same hook links a company's new red flags and each quarter's first preview or brief as
  timeline events. They are informational, never change a KPI, and are unique per thesis by ref.

**Alerts.** `thesis_trigger` reads only the alert owner's theses. Its key is
`thesis_kpi:{kpi}:{state}:{period_end}`, so a value flapping within one period notifies once per
state. Its text is the user's own label and threshold plus the cited value.

**Privacy (SEC-TH-002).** Thesis text, labels, notes and draft notes never enter log lines,
metric labels or error reports:
- Log lines carry ids and counts.
- `llm_calls` gets token counts only.
- A failed draft call logs the exception type, not its message, since a provider error can echo
  the request.
- An integration test captures stdout, the log records and `/metrics` around every write and
  checks that a marker string never appears.

**No AI verdicts.**
- The only model use is "Draft from my notes" (`thesis_draft_v1`): the user's notes are
  untrusted data, and the model sees the registry and those notes only.
- Every suggested KPI is re-validated against the registry and the unit checks; a stance is
  never read; title, label and rationale pass the advice, prediction and new thesis-verdict
  guards ("playing out", "at risk", "looks wrong"…).
- Nothing is saved until the user accepts.
- KPI states are the only verdict words the app uses.

**Markdown** is rendered by a small parser that builds React elements, so it is safe by
construction:
- raw HTML shows as text;
- only http(s) links are kept, opened with `noopener noreferrer`;
- images are never loaded.

## Consequences

**What this gives us:** a private notebook that keeps score deterministically, with a quiet
timeline and one alert per real change. A real gemini-3.8-flash draft from injected notes used
only registry metrics and suggested no stance.

**What it costs:**
- A user's threshold edit never notifies, even if it flips the state; the KPI table shows the new
  state instead.
- The draft rate limit is per API process, like the brief limit (ADR-0048).
- The registry is curated, so tracking a new metric means a code change.
- The markdown subset is small: no tables or nested lists.

**What would make us revisit it:** sharing theses (out of scope), user-defined formulas, or a
second API process (move the limiter to Redis).
