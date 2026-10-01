# Phase 6a — Company Comparison & Portfolio Analysis

**Prerequisites:** the MVP Definition of Done in the main spec (§36) should be met first — this
is explicitly a post-MVP phase. Requires Phase 1c (metrics), Phase 1d (prices), Phase 3a
(citations) to be solid, since comparison/portfolio features reuse all of them.
**Blocks:** nothing — this is an optional enhancement phase.
**Full spec sections:** §37.1 (company comparison), §37.2 (portfolio analysis).

## Objective

Let a user compare companies side by side and analyze a hypothetical portfolio — both built on
the same deterministic-metrics-plus-cited-AI-commentary pattern as everything else, never a
buy/sell recommendation.

## Scope

### Company comparison

1. **Peer-set logic:** suggest comparable companies by SIC/industry code and market-cap band
   (e.g. NVIDIA vs AMD vs Intel).
2. **Calendarization:** align companies with different fiscal year ends onto a common
   comparison period before computing side-by-side metrics — don't naively compare NVIDIA's
   FY (ending January) against a calendar-year peer's Q4 without adjusting.
3. **Sector-normalized percentiles:** for each metric, compute where each company falls versus
   its peer set (reuses Phase 1c's `percentile_rank` utility).
4. **Comparison UI:** side-by-side charts for revenue growth, margins, P/E, FCF, debt, growth.
5. **AI commentary limits:** any AI-generated comparison text is restricted to differences it
   can cite — reuse Phase 3a's verification pipeline exactly, don't build a separate, looser
   path for this feature.
6. **New API/tool:** implement `compare_companies(tickers, metrics, period)` (already specified
   as a Phase 2c tool stub — build the real logic here) and the frontend Compare page (§27.1
   Page 8, deferred from Phase 4c/4d).

### Portfolio analysis

7. **Portfolio input:** user enters holdings as ticker + weight (e.g. NVDA 30%, AAPL 20%...).
8. **Deterministic portfolio metrics:** weighted average of underlying metrics, sector
   exposure, concentration (Herfindahl-Hirschman Index), and — using Phase 1d's price
   history — correlation and volatility across holdings. All computed in backend code, same
   rule as every other metric in this project: never let the LLM compute a portfolio number.
9. **Aggregated risk themes:** pull each holding's cited risk factors (from Phase 3b's report
   data) and surface common themes across the portfolio — still fully cited back to each
   company's filing.
10. **What-if weight changes:** let the user adjust weights and see the deterministic metrics
    recompute live (client-side recomputation from already-fetched per-company data is fine
    here; no need to round-trip to the backend for a weight change).
11. **Explicit non-advice framing:** every portfolio output is analysis, never a
    recommendation — no "you should rebalance," ever. Reuse the hedged-language rule from bull/
    bear factors (spec LGL-006).

## Out of scope for this file

No brokerage integration, no real portfolio tracking with live positions — this is an
analysis tool over user-entered hypothetical weights, not a portfolio management product
(see the main spec's explicit out-of-scope list, §4.2).

## Definition of Done

- [ ] Comparing NVDA/AMD/Intel shows correctly calendarized, percentile-ranked metrics
      side by side
- [ ] Any AI commentary in the comparison view passes the same citation verification as
      report generation — test this explicitly, don't assume it inherits the behavior
- [ ] A portfolio of 3+ holdings computes correct weighted metrics, concentration, and
      correlation/volatility deterministically
- [ ] Adjusting portfolio weights recomputes metrics without a full backend round-trip
- [ ] No output anywhere in this feature contains a buy/sell/hold recommendation — spot-check
      this in review, since it's easy for hedged language to drift toward advice
