# Phase 7d — Earnings-Quality Dashboard (Accruals, Cash Conversion, Beneish, Altman, Piotroski)

**Prerequisites:** 7b (quarterly/TTM) done. Phase 1c metrics, Phase 6a comparison done.
**Blocks:** 7e (red-flag panel consumes these scores), 7j (briefs mention them).
**Full spec sections:** §10.x (metrics), `TODO.md` ("earnings-quality dashboard"). Requirement IDs:
`FR-EQ-001` … `FR-EQ-012`, `DR-EQ-001` … `DR-EQ-004`.

## Objective

Give the analyst one place that answers: "do reported earnings turn into cash, and does the
accounting look aggressive?" Much of the math is already in `finance/metrics.py`
(`accruals_ratio`, `dso/dio/dpo/cash_conversion_cycle`, `dilution`, `fcf_conversion`,
`piotroski_f_score`, `altman_z_score`) but is only partly persisted by `ratio_builder` and not
shown anywhere together. Add the missing Beneish M-score, persist everything, and present it as
a dashboard with honest labelling.

**Honesty rule for this whole file.** Beneish, Altman and Piotroski are screening heuristics
calibrated on specific populations (Beneish on US manufacturers, Altman Z on manufacturers,
and both are poor fits for banks and insurers). The UI must say "screening signal", must show
the inputs, and must refuse to compute them where the model does not apply (`DR-EQ-001`).
Never render a bare verdict like "manipulator".

## Scope

### 1. Concept map additions (do this first; tests depend on it)

1. The Beneish and Altman inputs need tags missing from `concept_map_v1.yaml`: `retained_earnings`,
   `sga_expense`, `ppe_net` (property, plant & equipment, net), `income_tax_expense`,
   `current_assets`, `current_liabilities`, `receivables_net`, `total_liabilities`,
   `depreciation` (as a flow), `securities_available` (optional). Add each as a versioned
   addition (`concept_map_v2` if the file's versioning rule requires it, otherwise append and
   note in the ADR). For each new metric add: the preferred XBRL tags in priority order, a
   golden value for NVDA/AAPL in `golden_metrics.json` that you verify by hand against the
   filing, and a sector-applicability entry.
2. JPM has a concept override file; do **not** edit it unless a banking input is needed, and
   mark Beneish/Altman `not_applicable` for banks via `sector_applicability.yaml`.

### 2. Beneish M-score (new, `finance/beneish.py`)

3. Implement the 8-variable model from year t and t−1 data:
   DSRI (days sales in receivables index), GMI (gross margin index), AQI (asset quality
   index), SGI (sales growth index), DEPI (depreciation index), SGAI (SG&A index), LVGI
   (leverage index), TATA (total accruals to total assets).
   `M = −4.84 + 0.920·DSRI + 0.528·GMI + 0.404·AQI + 0.892·SGI + 0.115·DEPI − 0.172·SGAI +
   4.679·TATA − 0.327·LVGI`.
   **Verify the coefficients and the −1.78 screening threshold against Beneish (1999) or a
   second reputable source before coding, and cite that source in the module docstring and
   the ADR.** Do not trust this file's numbers blindly; coefficient typos are the commonest
   bug here.
4. Return a `BeneishResult` with each of the eight indices, the score, a `band`
   (`below_threshold | above_threshold | insufficient_data`), and the list of source IDs of
   every input. Division guards: when a denominator is zero or an input is missing, return
   `insufficient_data` and name the missing input. Never substitute zero.
5. Tests: a hand-computed worked example with exact expected Decimals (put the arithmetic in
   the test comment), a "neutral company" case where all indices ≈1 and TATA ≈0, a missing-input
   case, and a bank → not-applicable case. Include a property test: scaling all dollar inputs
   by the same factor leaves the score unchanged (units sanity).

### 3. Altman Z and Piotroski completeness

6. Verify `altman_z_score` uses the right model variant for the company type: original Z for
   public manufacturers; Z″ (non-manufacturer / emerging) for others; not-applicable for
   financials. Zones: original Z distress <1.81, grey 1.81–2.99, safe >2.99. Verify against a
   source and cite it. Do not silently pick a model: store `model_variant` on the result.
7. `piotroski_f_score` currently takes `YearFinancials` for current and prior. Make sure all
   nine criteria are individually exposed (`criteria: dict[str, bool | None]`), where `None`
   means "could not compute", and the total is only reported as a number when all nine are
   computable; otherwise report "n of 9 computable".

### 4. Persist and API

8. `ratio_builder._compute_year` persists only a subset today. Persist the following with
   `derived:{TICKER}:{metric}:FY{yr}` IDs and `inputs` lists: `accruals_ratio` (both balance-sheet
   and cash-flow method), `dso`, `dio`, `dpo`, `cash_conversion_cycle`, `fcf_conversion`,
   `dilution` (net share count change), `beneish_m`, `altman_z`, `piotroski_f`. Add TTM-based
   versions of `fcf_conversion` and `accruals_ratio` using 7b.
9. New endpoint `GET /companies/{ticker}/earnings-quality?years=5` returning, per fiscal year,
   each measure with: value, `status` (`ok | insufficient_data | not_applicable`), `band` where
   defined, `inputs` (source IDs), and a short static `explanation` string from a constants
   file (no LLM text). Additive; update `docs/api.md` + `make openapi`.
10. Peer context: for each measure include `peer_percentile` using the existing
    `percentile_rank` and `comparison/peers.py`, hidden when fewer than 3 peers exist
    (a percentile among two companies is noise).

### 5. Dashboard UI

11. New "Earnings quality" tab on the company page, using Section/Card primitives from the UI
    system. Layout: a row of five measure cards (accruals, cash conversion, dilution,
    Beneish, Altman/Piotroski), then a 5-year trend table, then an "inputs" disclosure showing
    every number used with its source ID (clicking opens the citation drawer).
12. Colour rule: **green/red mean gain/loss only.** Use the `warning` token for "above the
    Beneish threshold" and neutral tokens for everything else. A text label always accompanies
    colour.
13. A visible caveat strip under each score: "Screening heuristic. Calibrated on US
    non-financial companies. Not a conclusion about this company's accounting." Not-applicable
    states explain why (e.g. "Not computed for banks").
14. A cash-vs-earnings chart: net income vs operating cash flow vs FCF per year, with
    accruals ratio as a line. Uses the existing chart library.

### 6. AI usage (optional but bounded)

15. The report generator may mention these scores, but only by quoting backend-issued values
    with their source IDs; the existing number-verification (1% tolerance) applies. Add one
    sentence to the report prompt contract: "Scores are screening heuristics; never describe a
    company as committing fraud or manipulation." Add a test that a generated sentence
    containing "manipulat"/"fraud" attached to a Beneish value is rejected by the verifier or
    a new rule in `citation.advice`.

## Out of scope

Forensic ratios requiring segment or footnote data (7f), peer-adjusted Beneish, machine-learning
fraud models, quarterly Beneish, any score for banks/insurers, and a combined "quality score"
that blends the five measures (resist this; blended scores hide the inputs).

## Docs to update in the same PR

`docs/database.md` (new derived metrics), `docs/api.md`/`openapi.json`, concept-map docs,
`docs/ui.md` (new tab), spec Appendix H, and ADR-0042 (Beneish/Altman variant and threshold
choices with citations).

## Definition of Done

- [ ] New concept tags have hand-verified golden values for NVDA and AAPL
- [ ] Beneish coefficients/threshold verified against a cited source (quoted in the ADR);
      worked-example test passes with exact Decimals
- [ ] Missing or zero-denominator input yields `insufficient_data` naming the input, never zero
- [ ] Banks (JPM) show `not_applicable` for Beneish and Altman with a reason string
- [ ] Altman variant is recorded in the result; Piotroski exposes all nine criteria
- [ ] All listed derived metrics persisted with source IDs and resolvable `inputs`
- [ ] `GET /companies/{ticker}/earnings-quality` returns 5 fiscal years for NVDA and AAPL
      fixtures; peer percentile hidden when <3 peers
- [ ] Dashboard renders all states (ok / insufficient / not applicable) in Vitest; Playwright
      opens an input's citation drawer
- [ ] No red/green is used for non-gain/loss meaning; caveat strip is present
- [ ] A report sentence calling a company a "manipulator" or "fraud" is blocked (test)
- [ ] `make coverage` 100% on `app/finance/*`; docs and ADR-0042 written; `make check` clean
