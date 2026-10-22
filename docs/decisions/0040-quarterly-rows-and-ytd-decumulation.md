# ADR-0040: Quarterly rows are persisted and flow metrics are de-cumulated from YTD facts

- **Status:** Accepted
- **Date:** 2026-10-21
- **Spec refs:** §10.x, §36, FR-QT-001 … FR-QT-012, DR-QT-001 … DR-QT-004 (Appendix H), DR-022, CIT-003

## Problem

Only annual metrics and a derived Q4 for four metrics were stored, so every earnings-date
feature (earnings quality, valuation bands, guidance vs actual, briefs) would have had to
re-derive quarters itself. The derived Q4 operating cash flow never existed: it looked up Q1–Q3
as ~91-day facts, but a 10-Q reports its cash-flow statement year-to-date (182 and 273 days), so
Q2 and Q3 were never found and Q4 was silently skipped. Raw facts carry no `fiscal_period` (the
companyfacts `fp` belongs to the filing, and a 10-Q's prior-year comparatives share it), so the
quarter of a fact has to be worked out another way. NVIDIA's late-January year end rules out
calendar quarters, and its 2024 10:1 stock split showed that per-share figures from different
filings do not share a share basis.

## Decision

`app/finance/quarterly.py` places every fact on the company's own fiscal calendar: fiscal years
come from the 10-K full-year spans (plus the year in progress), and a period ending `d` days
into a fiscal year ends quarter `classify_duration(d)` (~91 = Q1, ~182 = Q2, ~273 = Q3, a full
year = Q4), whether it is a 3-month or year-to-date fact. Cash-flow metrics (tagged
`cash_flow_metrics` in the concept map) are de-cumulated (Q2 = 6M − 3M, Q3 = 9M − 6M, Q4 =
FY − 9M); income-statement flows are read as true quarters with Q4 = FY − (Q1 + Q2 + Q3);
balances are read at each quarter end; per-share figures and share counts are never derived
by subtraction. Selection keeps the as-reported rule (earliest filed unless amended), so
Q1+Q2+Q3+Q4 equals the stored FY value exactly. `quarterly_builder` persists the last 12 quarters
(`period_type` Q, `xbrl:`/`derived:{TICKER}:{metric}:Q{n}-FY{yr}`), every complete four-quarter
TTM (`period_type` TTM, `derived:…:TTM-Q{n}-FY{yr}`) with TTM ratios from TTM numerators and
denominators, and refreshes a new `metric_gaps` table with a reason for every quarter or window
it cannot produce; a missing input is never guessed and three quarters are never annualized.
Derived rows keep the existing record format (`formula_id`, `quality_flags.derived` formula
text, `quality_flags.inputs` source IDs); quarter inputs cite the raw fact (`xbrl:<fact_id>`)
and the annual figure its stored row. TTM EPS uses the four-quarter sum when all four quarterly
EPS exist, otherwise `FY_prior − YTD_prior + YTD_current`, taking each term's latest-filed
restatement so a split does not mix share bases (as-filed figures made NVIDIA's TTM EPS −2.28),
and flags `share_count_changed` when diluted shares move more than 5% across the window.
`get_latest_metrics` now reads only FY and LATEST rows, so a quarter of the year in progress
never displaces the annual figure used by valuation, portfolio and research.

## Consequences

Later Phase 7 work reads quarters and TTM from `financial_metrics` instead of re-deriving them,
and every quarterly number cites its inputs. `GET /companies/{ticker}/metrics/coverage` and the
Overview's quarterly toggle can say "3 of 4 quarters available" instead of showing an empty box,
and N/A for the sector (`sector_applicability.yaml`) stays distinct from missing data. A rebuild
writes about 300 quarterly and 170 TTM rows per company. Costs: a quarter is only found if some
filing reports a period ending on it; a split right after a 10-K, before later filings restate
the prior year, can still mix share bases in TTM EPS (the share-count flag is the safety net);
valuation multiples still use fiscal-year figures until Phase 7h switches them to TTM. Revisit
if a filer reports neither 3-month nor YTD periods, or if raw facts gain a reliable fiscal period.
