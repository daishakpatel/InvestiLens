# ADR-0043: Red flags are rule-based and versioned; no LLM classification

- **Status:** Accepted
- **Date:** 2026-10-22
- **Spec refs:** §10.x, §26.2, §37.4, Appendix H (FR-RF-001 … FR-RF-014, DR-RF-001 … DR-RF-003)

## Problem

Analysts want one place that says "stop and look": an auditor change, a non-reliance notice, a
going-concern warning, a late filing, an executive departure. A wrong flag costs trust both
ways. Calling a routine retirement "trouble" misleads, and missing a 4.02 notice is worse. Three
things make this hard:
- Going-concern wording often appears precisely to deny doubt.
- 8-K Item 5.02 mixes departures with appointments and pay plans.
- Re-running detection, or improving a rule, must not flood users with alerts about years-old
  filings.

## Decision

**Detection is deterministic.** The registry is `red_flag_taxonomy_v1` in
`backend/app/redflags/taxonomy.py`. Each rule is data plus a small matcher, keyed on one of:
- an 8-K item code (1.03, 1.05, 2.05, 2.06, 3.01, 4.01, 4.02, 5.01, 5.02), with titles and numbers
  checked against SEC Form 8-K "SEC 873 (02-25)";
- a form type (NT 10-K / NT 10-Q, i.e. Form 12b-25 under Rule 12b-25);
- a guarded phrase rule (going concern in 10-K/10-Q, material weakness in 10-K Item 9A, departures
  in Item 5.02);
- a stored figure (the 7d Beneish band; as-reported values that differ in a 10-K/A or 10-Q/A).

No model classifies anything.

The phrase regexes live in `redflags/patterns.py` rather than in the taxonomy file itself. The
going-concern classifier needs them too, and keeping them separate avoids an import cycle. Every
pattern carries a comment and an example string.

**Guards:**
- *Going concern* sentences are classified as negated (no flag), policy description (no flag),
  conditional (`going_concern_risk_language`, info), alleviated by management's plans
  (`going_concern_alleviated`, warning), or plain doubt (`going_concern`, critical).
- *Departures* need a departure verb in the item's own text with the title removed. Award or
  agreement terms and biographies are skipped. Roles come only from the departure sentence (5.02(b)
  roles); none found means `exec_change_unspecified`. Names are never extracted.
- *Item codes* come from the filing index, falling back to parsed headings (ADR-0041), so a 5.07
  vote is never a 5.02.

**Storage:** `red_flags` holds one row per (company, rule, taxonomy version, filing, paragraph).
- The unique key is NULLS NOT DISTINCT, because a late notice quotes no paragraph. Inserts are
  `ON CONFLICT DO NOTHING`, so re-runs are no-ops.
- The key includes `taxonomy_version`, which the task's key omitted. Without it, a new version
  could not add rows while keeping the old ones.
- A new version's rows copy the **first** detection time of the same event. Old rows stay for
  audit, and the API serves only the current version.
- `event_date` is the filing date (`filings.filing_date`, the EDGAR acceptance date); the
  acceptance timestamp itself stays on `documents.published_at`.
- Source IDs are `redflag:{TICKER}:{rule_key}:{accession}`, one flag per rule per filing. They
  resolve to the quoted text as a `text_chunk` with the filing as the deep link, so the source
  contract is unchanged.

**Alerts:** the `red_flag` alert keys events by that source ID and fires on first detection. It
skips flags whose filing is more than 7 days older than its detection: a backfill, a newly added
company or a new rule over old filings is history, not news. The body is only "Reported: {label}
(filed {date})." The registry's event-key test now also accepts a key that is its own
type-unique evidence ID.

## Consequences

- Every flag can be explained from fixed text and checked by tests (3+ positives and 3+ negatives
  per rule).
- The phrase rules will miss unusual wording, and could still fire on an odd sentence. They were
  tuned on the real 8-Ks in the dev store (NVIDIA, Intel, JPMorgan, AMD, Apple), and the misses on
  award terms and bios were fixed. The cost of a miss is lowered by keeping labels neutral and
  every flag quoted.
- Going-concern and material-weakness positives are synthetic, because no dev company reports
  one. Real examples should be added when a company that does is ingested.
- Revisit if:
  - a phrase rule needs context beyond one sentence;
  - the SEC adds or renumbers 8-K items (bump the version);
  - users want flags for older filings in alerts (`FRESH_DAYS`).
