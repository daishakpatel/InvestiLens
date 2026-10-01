# Phase 1d — Price & Corporate Action Ingestion

**Prerequisites:** Phase 0 complete. Can run in parallel with Phase 1a–1c.
**Blocks:** price-dependent metrics in Phase 1c (P/E, market cap, EV — those functions exist
already, they just need real price rows to run against), Phase 4c (price charts).
**Full spec sections:** §11.6 (price correctness rules), §7 (price provider), §23.1
(`price_history`, `corporate_actions` tables — already created in Phase 0b).

## Objective

Get real daily price history and corporate actions flowing into the tables Phase 0b already
created, through a real provider client (behind the `PriceProvider` interface from Phase 0c).

## Scope

1. **Implement the real `PriceProvider`** for whichever provider was chosen in ADR-0007
   (Phase 0a). Same reliability bar as every other provider client: timeouts, retry with
   backoff, circuit breaker, structured logging, response caching.
2. **Ingest daily price history** into `price_history`: `open, high, low, close, adj_close,
   volume`. Store both raw close and split/dividend-adjusted close (DR-025) — raw is used for
   P/E and market cap (paired with contemporaneous shares/EPS), adjusted is used for return
   charts. Be explicit in code comments about which one each caller should use.
3. **Corporate actions:** ingest splits and dividends into `corporate_actions`
   (`action_type`, `ex_date`, `ratio_or_amount`). Cross-check against anything already
   recorded from filings in Phase 1b.
4. **Market cap calculation input:** shares outstanding should come from the filing cover
   page / `dei:EntityCommonStockSharesOutstanding` fact (already in `financial_facts` from
   Phase 1a), as of the record date — not guessed from price data. Handle multi-class
   companies (Alphabet A/B/C) by summing classes correctly; this is a real edge case, don't
   skip it if you seed Alphabet later.
5. **Freshness:** daily EOD refresh (after market close + provider delay); update
   `data_freshness` for the `price` source per company.
6. **Backfill:** at minimum 5 years of daily history for seed companies, to support the
   5-year valuation bands used later in Phase 3b/report generation.
7. **Split-adjustment retroactivity:** verify that a split (e.g. NVIDIA's 2024 10-for-1) is
   correctly reflected in adjusted price history and doesn't distort historical P/E when
   paired with as-reported EPS from before the split — this is a common bug, write a specific
   test for it.

## Out of scope for this file

Don't recompute the P/E/market cap/EV formulas — those already exist from Phase 1c. This file
only supplies the price inputs they need. Don't build valuation percentile bands yet (Phase 3b
or Phase 6, depending on how it's scheduled) — just make sure 5 years of clean price history
exists to support them later.

## Definition of Done

- [ ] `price_history` has 5+ years of daily data for each seed company, with both raw and
      adjusted close populated
- [ ] `corporate_actions` correctly records NVIDIA's 2024 split
- [ ] A test confirms P/E computed around the split date doesn't break (uses the right EPS
      basis for the right side of the split)
- [ ] Market cap for a multi-class company (if seeded) correctly sums share classes
- [ ] `data_freshness` reflects a real `last_success_at` for the price source
- [ ] Provider client has the same reliability bar (timeout/retry/circuit breaker/logging) as
      every other provider in the project
