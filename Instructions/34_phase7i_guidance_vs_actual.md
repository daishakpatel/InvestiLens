# Phase 7i — Guidance vs Actual Tracker

**Prerequisites:** 7a (alerts), 7b (quarterly actuals), 7c (EX-99.1 press releases ingested).
**Blocks:** 7j (earnings brief uses the comparison).
**Full spec sections:** §37.3 (earnings analysis — guidance tracking, with the licensing
caveat), `TODO.md` ("guidance vs actual needs EX-99.1"). Requirement IDs: `FR-GD-001` …
`FR-GD-012`, `DR-GD-001` … `DR-GD-003`, `AGT-GD-001`.

## Objective

Track what management *said it expected* and compare it with what happened. This is a core
analyst habit: a company that repeatedly guides conservatively and beats is different from one
that misses. The comparison is deterministic. The only fuzzy step is **extracting the guidance
number from the press release**, and that step is fenced with quote-and-verify rules.

**Licensing note.** Company guidance comes from the company's own public press release, which is
fine to store and show. Analyst **consensus estimates** come from paid data vendors; this app has
no licensed source (no ADR covers estimates; record the "no consensus data" decision in this file's ADR), so "beat/miss versus consensus" is explicitly out of scope and
must not be approximated. Only "versus the company's own guidance" is built.

## Scope

### 1. Data model

1. `guidance_items(id, company_id, source_document_id, paragraph_id, issued_at, fiscal_year,
   fiscal_period, metric, low, high, point, unit, basis, quote, confidence_state, taxonomy_version,
   created_at)`.
   - `metric` is from a fixed list `guidance_metric_v1`: `revenue`, `gross_margin`,
     `operating_margin`, `eps_gaap`, `eps_non_gaap`, `operating_expenses`, `capex`,
     `tax_rate`, `free_cash_flow` (extend sparingly).
   - `low`/`high` for ranges, `point` for single values; exactly one form is populated.
   - `basis`: `gaap | non_gaap | unspecified`. Non-GAAP guidance is **not comparable** with
     GAAP actuals and must never be compared to them (`DR-GD-001`).
   - `unit`: `usd | ratio | percent_of_revenue`; money in raw USD, ratios as decimals.
   - `confidence_state`: `verified | rejected`. Only `verified` rows are shown.
2. `guidance_outcomes(guidance_id, actual_value, actual_source_id, delta_vs_low,
   delta_vs_high, delta_vs_mid, result, computed_at)` where `result` is
   `above_range | within_range | below_range | not_comparable | actual_unavailable`.

### 2. Extraction pipeline

3. Input: earnings-release documents (`document_type='earnings_release'`) from 7c, specifically
   the "outlook"/"guidance"/"business outlook" section, located by heading keywords, with a
   regex pre-filter on sentences containing a metric word and a number. The LLM sees only those
   candidate sentences, not the whole release.
4. The model returns candidate items `{metric, low, high, point, unit, basis, period_text,
   quote}`. The verifier then:
   a. confirms `quote` is a verbatim substring of the cited paragraph;
   b. confirms the extracted numbers appear in the quote after normalising "$5.4 billion",
      "$5,400 million", "5.4B" using the existing unit helpers (do not reimplement
      `filings/units.py`);
   c. resolves `period_text` ("second quarter of fiscal 2027", "for fiscal 2027") to
      `fiscal_year`/`fiscal_period` **using the company's fiscal calendar**, and rejects the item
      if it cannot be resolved unambiguously;
   d. sets `basis` by a deterministic keyword check ("non-GAAP", "GAAP") in the same sentence,
      overriding the LLM if they disagree.
   Items failing any check are stored as `rejected` with a reason, for audit, never shown.
5. Tolerance wording ("$7.5 billion, plus or minus 2%") produces `low = point × (1 − 0.02)`
   and `high = point × (1 + 0.02)` only when the release states it that way; store the original
   quote and set `derived_range=true` (add the column). If the wording is at all ambiguous,
   reject the item.
6. Prompt `guidance_extract_v1` treats the release as untrusted data; includes the injection
   test; versioned and cached by `(document_id, prompt_version, model)`.

### 3. Outcome computation (pure Python)

7. When the quarter's actuals exist (7b quarterly rows; or FY rows for annual guidance), compute
   outcome per guidance item. Mapping `guidance.metric → financial_metrics.metric` is an
   explicit table in code with a unit test. `gross_margin` actual = gross_profit / revenue
   computed from the quarter's rows; non-GAAP basis → `not_comparable` always.
8. `delta_vs_mid` = actual − midpoint (money) or in ratio points; also store the percentage
   versus midpoint for display. Use Decimal throughout.
9. A guidance item superseded by a later release for the same period (companies update
   guidance) is marked `superseded_by`; the tracker uses the **initial** guidance for the
   headline outcome and shows revisions in a list. (This avoids "beating" a lowered bar.)
10. `FinancialMetric` actual lookups use the same source IDs the rest of the app cites, so a click
    on "actual" goes to the metric's evidence.

### 4. Track record

11. Per company compute over the last 8 quarters with verified guidance: `n_comparable`,
    `n_above`, `n_within`, `n_below`, and average `delta_vs_mid` for revenue. Show only when
    `n_comparable ≥ 4`; otherwise say "insufficient history (n=3)".
12. Label wording is positional ("Revenue came in above the guided range in 6 of 8 quarters").
    No "sandbagging", "conservative", "reliable" characterisations (advice/characterisation test).

### 5. Alerts

13. Register `guidance_miss` in the 7a registry: fires when a quarterly outcome is `below_range`
    for a tracked metric. Params: `metrics` (default revenue, eps_gaap). `event_key` =
    `guidance_outcome:{guidance_id}`. Message template: "{metric} came in below the guided range
    ({actual} vs {low}–{high}). Source: {source_id}." Also allow `above_range`.

### 6. API & UI

14. `GET /companies/{ticker}/guidance?fiscal_year=` returns items with outcome and revisions;
    `GET /companies/{ticker}/guidance/track-record`. Additive; update docs and openapi.
15. UI "Guidance" Section on the Earnings view: a table (period, metric, guided range, actual,
    result chip with text, delta), a range-vs-actual dot plot for revenue, and the track-record
    line. Rows open the citation drawer showing the exact guidance quote in the press release.
16. Non-comparable rows are shown with an explanation ("Guided on a non-GAAP basis; GAAP actual
    not comparable"), not hidden.

## Out of scope

Consensus estimates, surprise percentages versus Street, forward-looking AI predictions of the
next guide, qualitative guidance ("we expect strong demand"), segment-level guidance, and
transcripts (not ingested).

## Docs to update in the same PR

`docs/database.md`, `docs/api.md`/`openapi.json`, `docs/ui.md`, prompt registry, spec Appendix H
(and a note in §37.3 that estimates remain unbuilt), ADR-0047 (company-guidance-only scope,
non-GAAP exclusion, initial-guidance rule).

## Definition of Done

- [x] From the NVDA EX-99.1 fixture, the revenue outlook (range) is extracted with a verbatim
      quote, correct low/high in raw USD, and correct fiscal period
- [x] A fabricated number or quote in a recorded LLM response is rejected and stored as
      `rejected` with a reason
- [x] GAAP/non-GAAP: a non-GAAP guidance item is never compared to a GAAP actual
      (`not_comparable`), proven by test
- [x] Period resolution uses the fiscal calendar (NVDA's year ending January) and rejects
      ambiguous wording
- [x] Outcome computation covers above, within, below, unavailable; midpoint deltas use Decimal
- [x] A later revision is stored; headline outcome uses the initial guidance
- [x] Track record is hidden when `n_comparable < 4`, shows `n` otherwise
- [x] `guidance_miss` alert fires once for a simulated below-range quarter
- [x] Prompt-injection fixture does not alter extraction
- [x] No characterisation words ("sandbag", "conservative") appear in any template (test)
- [x] Guidance UI shows populated, non-comparable and insufficient-history states
- [x] Docs and ADR-0047 written; `make check` and `make openapi` clean
