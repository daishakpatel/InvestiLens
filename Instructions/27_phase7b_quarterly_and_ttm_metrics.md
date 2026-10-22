# Phase 7b — Quarterly & TTM Metrics (and the Q4 Operating-Cash-Flow Bug)

**Prerequisites:** Phase 1c (financial metrics) and 1b (concept map) done. No dependency on 7a.
**Blocks:** 7d (earnings quality needs quarterly series and TTM), 7h (valuation bands need TTM
EPS/EBITDA), 7i (guidance vs actual compares against quarterly actuals), 7j (briefs).
**Full spec sections:** §10.x (financial metrics), §36 (MVP DoD). Requirement IDs:
`FR-QT-001` … `FR-QT-012`, `DR-QT-001` … `DR-QT-004`.

## Objective

Persist real **quarterly** and **trailing-twelve-month (TTM)** metrics, and fix a known bug: the
derived Q4 operating cash flow never completes. Today `finance/builder.py` stores annual metrics
plus a derived Q4 for four metrics only. Everything an analyst does around an earnings date is
quarterly, and `TODO.md` lists "quarterly/TTM not persisted" as the top data gap. Later Phase 7
files would each have to re-derive quarters on their own; do it once, here, with tests.

## Background: why this is not trivial

10-Q filings report income-statement items per quarter, but **cash-flow items year-to-date**. A
Q2 10-Q reports operating cash flow for the 182 days ended in Q2, not for Q2 alone. Q3 reports
273 days. The 10-K reports 365. To get a single quarter you must de-cumulate:

- Q1 = YTD(91d)
- Q2 = YTD(182d) − YTD(91d)
- Q3 = YTD(273d) − YTD(182d)
- Q4 = FY − YTD(273d)

The current `_derive_quarter_four` fetches Q1–Q3 using `select_metric(..., quarter=True)`, which
only matches facts with a ~80–100 day duration (`periods.QUARTER = (80, 100)`). YTD cash-flow
facts have durations of ~91/182/273 days, so Q2/Q3 are never found and Q4 OCF is silently
missing. `derivation.decumulate` exists but is not wired in. Flow items on the income statement
*do* come as true quarters, so they work today. This file keeps both paths correct.

## Scope

### 1. Period model

1. Extend `periods.py` with `classify_duration(days) -> PeriodShape` returning one of
   `QUARTER (80–100)`, `YTD_2Q (170–195)`, `YTD_3Q (260–285)`, `FULL_YEAR (350–380)`, or
   `OTHER`. Keep existing constants; add the YTD windows as named constants with a comment
   citing the day counts above.
2. Selection must stay deterministic: when multiple facts exist for the same
   `(concept, period_end, shape)`, keep the existing rule (earliest-filed wins unless an
   amendment) so restatements remain as-reported (`DR-QT-001`).

### 2. De-cumulation for cash-flow (flow) metrics

3. Wire `derivation.decumulate` into the builder for metrics tagged as cash-flow flows in the
   concept map (`operating_cash_flow`, `capex`, `stock_based_compensation`,
   `depreciation_amortization`, `share_repurchases`, `dividends_paid`). Check
   `concept_map_v1.yaml` for which tags exist; add only tags a real fixture needs, no
   speculative ones.
4. For each fiscal year build `Q1..Q4` per cash-flow metric from YTD facts. If any required
   YTD fact is missing, **do not guess**: skip that quarter, record a row in a new
   `metric_gaps` structure (see §5) with the reason (`missing_ytd_2q`, …), and continue.
5. Fiscal year-end handling: do not assume calendar quarters. Use the company's
   `fiscal_year_end` (NVDA ends late January) and the filing's `fiscal_period` field. The
   conventions rule applies: fiscal fields are stored separately and never inferred from
   calendar dates.
6. Q4 derivation for income-statement flows remains `FY − (Q1+Q2+Q3)`. Extend
   `_Q4_METRICS` from 4 metrics to every flow metric the app displays (add `gross_profit`,
   `cost_of_revenue`, `rd_expense`, `sga_expense` only if the concept map already maps
   them; otherwise add the tag and a fixture case in 1b style).

### 3. Persist quarterly rows

7. Persist every quarter (`period_type='Q'`) for the last 12 quarters per company, not just
   Q4. `financial_metrics` already allows `Q`; no new column. Source IDs:
   `xbrl:{TICKER}:{metric}:Q{n}-FY{yr}` for facts read directly from a 10-Q and
   `derived:{TICKER}:{metric}:Q{n}-FY{yr}` for anything computed (de-cumulated or Q4).
   Document the scheme in `docs/database.md` next to the existing ones.
8. Derived rows keep a `formula` string and `inputs` list (the source IDs of the facts they
   came from) so the citation drawer can show "Q3 OCF = 9M YTD − 6M YTD" with both inputs
   linked. Reuse the existing derived-metric record format; do not invent a new one.

### 4. TTM metrics

9. Implement `ttm_for(metric, as_of_quarter)` using `metrics.ttm_sum`: sum of the latest four
   consecutive quarters for flow metrics (revenue, net income, OCF, FCF components,
   EBITDA components). For stock metrics (cash, debt, equity) TTM means "latest balance",
   not a sum.
10. **TTM EPS** uses the identity `FY_prior − YTD_prior + YTD_current` when only YTD facts
    exist, and the four-quarter sum when quarterly EPS exist. Never sum EPS across quarters
    if share count changed materially without noting it: when diluted shares move by more
    than 5% between the first and last quarter in the window, set `quality_flag =
    'share_count_changed'` on the row instead of silently summing.
11. Persist TTM as `period_type='TTM'` with `period_end` = latest quarter end. A TTM row is
    only produced when **all four** quarters are present. A three-quarter "annualized" number
    must never be stored as TTM (`DR-QT-002`).
12. Derived TTM ratios (TTM gross margin, TTM FCF margin, TTM operating margin, TTM ROIC)
    compute from TTM numerator and TTM denominator, never by averaging quarterly ratios
    (`DR-QT-003`). Add a unit test with unequal quarter sizes where averaging gives a
    visibly wrong answer.

### 5. Gaps are first-class, not silent

13. New table `metric_gaps(company_id, metric, period_label, reason, detected_at)` with a
    unique key on `(company_id, metric, period_label)`; refreshed on every metrics run.
    Expose via `GET /companies/{ticker}/metrics/coverage` returning, per metric, which
    quarters exist and which are missing and why. The frontend shows a small "3 of 4
    quarters available" note on any TTM-dependent card instead of an empty box
    ("never fail silently").
14. Sector applicability (`sector_applicability.yaml`) still decides what is N/A. A bank's
    gross margin is "not applicable", not a "gap". Gaps and N/A must render differently.

### 6. API and UI

15. Extend the existing metrics endpoint with `?period_type=Q|TTM|FY` and
    `?limit=` (default 8 quarters, max 20). Additive; update `docs/api.md`, run
    `make openapi`.
16. Overview tab: add a quarterly/TTM toggle on the existing revenue and margin charts.
    Quarterly bars with a TTM line. Hover shows the source ID and, for derived rows, the
    formula. No new chart library.

## Out of scope

Quarterly balance-sheet ratios that need averages (ROIC with average capital) beyond what 1c
already computes at annual granularity; seasonally adjusted series; segment quarterly data;
5-year averages (covered in 7h). Do not backfill beyond 12 quarters.

## Docs to update in the same PR

`docs/database.md` (source-ID schemes, `metric_gaps`), `docs/api.md`/`openapi.json`,
`docs/architecture.md` (one paragraph: how quarters are derived), spec Appendix H, and
ADR-0040 ("quarterly rows are persisted and flow metrics are de-cumulated from YTD facts").

## Definition of Done

- [ ] For NVDA, AAPL and JPM fixtures, `operating_cash_flow` has persisted Q1–Q4 for at least
      the two most recent fiscal years, and Q1+Q2+Q3+Q4 equals the 10-K FY value exactly
      (Decimal equality test, `DR-QT-004`)
- [ ] A regression test reproduces the old bug (Q4 OCF missing) on the pre-fix code path and
      passes after the fix
- [ ] Missing YTD input yields no quarter and a `metric_gaps` row with a reason, never a
      guessed value
- [ ] NVDA's January fiscal year end produces correctly labelled `FY`/`Q` rows (unit test
      checking `fiscal_period` independent of calendar month)
- [ ] TTM rows exist only when four quarters are present; a three-quarter case produces no
      TTM row and a gap
- [ ] TTM margin is computed from TTM sums; the unequal-quarters test proves it
- [ ] `share_count_changed` quality flag is set when diluted shares move >5% across the window
- [ ] Derived quarterly rows carry `formula` and `inputs`, and each input resolves through
      `citation.resolve_source`
- [ ] `GET /companies/{ticker}/metrics/coverage` reports present and missing quarters; N/A
      (sector) is distinguishable from missing (data)
- [ ] Overview quarterly/TTM toggle renders against fixtures, with a "n of 4 quarters" note
      where applicable
- [ ] `make coverage` still shows 100% on `app/finance/*`; docs and ADR-0040 written;
      `make check` and `make openapi` clean
