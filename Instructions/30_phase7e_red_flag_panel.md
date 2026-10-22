# Phase 7e — Red-Flag Panel (8-K Items, Late Filings, Going Concern, Auditor Changes)

**Prerequisites:** 7a (alert registry), 7c (full 8-K item codes, NT forms), 7d (earnings-quality
scores) done.
**Blocks:** 7j (briefs show new flags), 7k (thesis triggers can reference flags).
**Full spec sections:** §10.x (filings), §37.4 (new-risk alert), §26.2 (alerts). Requirement IDs:
`FR-RF-001` … `FR-RF-014`, `DR-RF-001` … `DR-RF-003`.

## Objective

Surface, in one panel, the events an analyst treats as "stop and look": an auditor resignation,
a non-reliance on prior financials, a going-concern warning, a restructuring or impairment, a
late-filing notice, an executive departure. Every one is detected **deterministically** from
structured filing data (8-K item codes, form types, XBRL, fixed phrase rules), cited to the
filing, and shown with neutral language. No AI judges whether something is "bad".

**Honesty rule.** A flag means "this event is reported," not "this company is in trouble." Copy
must say "reported" and link the filing. Many flags are routine (executive transitions, planned
restructurings). Severity describes *how closely an analyst would want to read it*, not
whether it is negative.

## Scope

### 1. Flag taxonomy (`backend/app/redflags/taxonomy.py`, versioned `red_flag_taxonomy_v1`)

1. Define each flag as `RedFlagRule(key, label, severity, source, matcher, explanation)`.
   Initial rules (keys → trigger):
   - `auditor_change` (warning) → 8-K Item **4.01**
   - `non_reliance` (critical) → 8-K Item **4.02** (non-reliance on previously issued financials)
   - `late_filing_notice` (warning) → form **NT 10-K / NT 10-Q**
   - `exec_departure` (info) → 8-K Item **5.02** where the section text matches departure
     phrasing (see below)
   - `impairment` (warning) → 8-K Item **2.06**
   - `restructuring` (info) → 8-K Item **2.05** (costs associated with exit activities)
   - `delisting_notice` (critical) → 8-K Item **3.01**
   - `bankruptcy` (critical) → 8-K Item **1.03**
   - `material_cyber_incident` (warning) → 8-K Item **1.05**
   - `change_in_control` (info) → 8-K Item **5.01**
   - `going_concern` (critical) → phrase rule on 10-K/10-Q text (below)
   - `material_weakness` (warning) → phrase rule on 10-K Item 9A
   - `beneish_above_threshold` (info) → 7d result `above_threshold`
   - `restatement_in_xbrl` (warning) → same fiscal period reported with different values in an
     amended filing (the builder already keeps as-reported rows; compare them)
   Check each item number against the SEC Form 8-K instructions before coding and cite them in
   the taxonomy docstring. Do not rely on this list from memory.
2. Rules are data plus small matcher functions, in one registry, so adding a rule is a
   single entry plus a test, mirroring how topics work in `filings/topics.py`.

### 2. Phrase rules with guards (the hard part)

3. **Going concern** (`redflags/going_concern.py`). Match "substantial doubt" near "ability to
   continue as a going concern" within one sentence. Then apply guards that suppress the
   flag, each with its own test:
   - **Negation:** "no substantial doubt", "did not raise substantial doubt", "alleviated
     substantial doubt" → not flagged. (Companies often include the phrase to say there is
     *no* doubt.)
   - **Hypothetical/risk-factor language:** "if we are unable to … there could be substantial
     doubt" → classify as `risk_language`, not `going_concern`; shown at a lower tier with a
     different label.
   - **Management plans:** "substantial doubt … alleviated by management's plans" → flag as
     `going_concern_alleviated`, wording changes to reflect that.
   Output includes the exact sentence and its `paragraph_id` so the UI quotes it.
4. **Executive departure** (Item 5.02): detect resignation/termination/retirement/"will step
   down" within the section, extract the role keyword set (CEO, CFO, COO, CAO, director) and
   report the roles; **do not** attempt to extract the person's name via an LLM. Use the section
   text snippet as the evidence. If no role keyword is found, the flag still fires as
   `exec_change_unspecified`.
5. All phrase patterns live in the taxonomy file as compiled regexes with comments and an
   example string; the test file asserts at least three positives and three negatives per
   pattern, taken from real fixture text where possible and synthetic text otherwise (labelled).

### 3. Persistence

6. New table `red_flags(id, company_id, rule_key, taxonomy_version, filing_id, document_id,
   paragraph_id NULL, detected_at, event_date, severity, snippet, payload JSONB)`.
   Unique `(company_id, rule_key, filing_id, paragraph_id)`. `event_date` is the filing's
   acceptance date, not the detection time.
7. Detection runs as a post-parse step in `parse_documents` for new documents and as a nightly
   backfill (`make redflags-backfill`), idempotent through the unique key. Re-running with a new
   taxonomy version creates new rows and leaves older ones for audit; the API serves the latest
   version only.
8. Source IDs: `redflag:{TICKER}:{rule_key}:{accession}` registered with
   `citation.resolve_source` so the citation drawer can display the filing snippet and a link.
   Update `resolve_source` ordering and its tests; do not break existing prefixes.

### 4. API

9. `GET /companies/{ticker}/red-flags?since=&severity=&limit=` returns flags newest-first, each
   with `label`, `severity`, `event_date`, `snippet`, `filing` summary and `source_id`.
   `GET /red-flags?watchlist=true` for a cross-company feed over the caller's watchlist.
   Additive; update docs and openapi.
10. An empty result returns an explicit `{"items": [], "last_scanned_at": ...}` so the UI can
    say "Scanned through <date>; nothing reported" rather than showing a blank panel.

### 5. Alerts

11. Register a `red_flag` event type in the 7a registry. Params: `min_severity`
    (`info|warning|critical`, default `warning`) and optional `rule_keys`. `event_key` is the
    source ID. Body text uses the neutral template "Reported: {label} (filed {date})" only.

### 6. UI

12. A "Red flags" Section on the Overview tab (and a count badge on the tab). Rows: severity
    chip (use `warning` token for warning/critical; never green/red), label, date, quoted
    snippet (collapsed to two lines), "Open filing" link. Show the rule's `explanation` in a
    tooltip so a reader learns what Item 4.02 means.
13. Empty state shows last-scanned date. Clicking a row opens the citation drawer.
14. A small "How to read this" disclosure: flags are reported events, not conclusions.

## Out of scope

Natural-language summarisation of flags, sentiment scoring, litigation tracking, SEC
enforcement/comment-letter ingestion, insider-trading flags (Form 4 not ingested), and
cross-company contagion scoring.

## Docs to update in the same PR

`docs/database.md` (`red_flags`), `docs/api.md`/`openapi.json`, `docs/ui.md`, taxonomy reference
(a table of rules, their triggers and their SEC sources), spec Appendix H, ADR-0043 (flags are
rule-based and versioned; no LLM classification).

## Definition of Done

- [ ] Every rule in `red_flag_taxonomy_v1` has a documented SEC source and ≥3 positive and
      ≥3 negative tests
- [ ] Going-concern guards: negated, hypothetical and alleviated sentences each produce the
      correct (or no) flag in tests
- [ ] An 8-K fixture with Item 4.02 yields a `non_reliance` flag with the right filing and
      date; a 5.07 (shareholder vote) 8-K yields **no** exec-departure flag (guards the old
      item-code collision)
- [ ] An NT 10-K fixture yields `late_filing_notice`
- [ ] Re-running detection twice creates no duplicates; a new taxonomy version adds rows and
      the API returns only the latest
- [ ] `redflag:` source IDs resolve in the citation drawer with snippet and filing link
- [ ] The `red_flag` alert fires once for a simulated new 4.02 filing and respects
      `min_severity`
- [ ] Panel renders populated, empty (with scanned-through date) and error states; no red/green
      colour used for severity
- [ ] Copy review: no flag text implies wrongdoing; `contains_advice` is false on all
      templates
- [ ] Docs and ADR-0043 written; `make check` and `make openapi` clean
