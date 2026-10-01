# Phase 1b — XBRL Concept Map & Fiscal Calendars

**Prerequisites:** `05_phase1a_sec_ingestion.md` done — real `financial_facts` rows must
exist for at least NVDA, AAPL, and JPM.
**Blocks:** `07_phase1c_financial_metrics.md`, which consumes the canonical concept
selections this file produces.
**Full spec sections:** §11 (financial data correctness rules — this file implements DR-020,
021, 022, 023, 026), Appendix B (starter concept map), Appendix C (sector applicability).

## Objective

Turn raw, inconsistent XBRL tags into clean, canonical, per-company-per-period values that
Phase 1c can safely run formulas over. This is the single most important correctness layer in
the whole project — get it wrong and every downstream number is wrong.

## Scope

1. **Build `concept_map_v1.yaml`** starting from spec Appendix B (copy it as-is — it's already
   a reasonable starter). It maps canonical names (`revenue`, `net_income`, `total_assets`,
   etc.) to an ordered list of XBRL tags to try, first-available-wins.
2. **Concept selection logic** (DR-020): for a canonical metric + period, walk the tag list in
   priority order, take the first tag with a value in a context matching that period, and
   record the chosen tag as `source_tag` alongside the value. Validate this logic against the
   `golden_metrics.json` fixture from Phase 0d — if the selected value doesn't match the
   hand-verified golden value, the map or the logic is wrong; fix it before moving on.
3. **Company-level overrides**: support `concept_overrides/{cik}.yaml` for companies whose
   XBRL doesn't follow the default pattern (banks are the obvious first case — build JPM's
   override file now, since it's one of your seed companies).
4. **Fiscal calendars (DR-021):** populate `fiscal_calendars` per company — fiscal year end,
   quarter boundaries, 52/53-week handling. NVIDIA's FY ends the last Sunday of January —
   verify your calendar logic reproduces that exactly against the golden fixture.
5. **Q4 derivation (DR-022):** 10-Ks report only annual figures. For flow items (revenue, net
   income, cash flow lines), compute Q4 = FY − (Q1+Q2+Q3), flag the resulting row
   `is_derived = true`, and store the four input fact IDs for lineage. For 10-Q cash-flow
   statements (which are cumulative YTD), de-cumulate before computing quarterly deltas.
   Balance-sheet items are instants — Q4 balance = fiscal year-end balance, not derived.
6. **Restatements (DR-023):** every fact keeps `filed_date`/`accession_number`; when a 10-K/A
   restates a number, insert a new row rather than overwriting, and mark which one `is_latest`.
7. **Units (DR-024):** normalize XBRL `decimals`/`scale` to raw units on ingest; if a fact's
   unit is inconsistent with its concept's expected unit (e.g. a per-share tag with a currency
   unit), flag it in `data_quality_issues` rather than storing a silently wrong number.
8. **Share counts & splits (DR-026):** use diluted weighted-average shares and diluted EPS as
   reported; don't retroactively adjust for splits here — that's a display/comparison concern
   for Phase 1c, but record `corporate_actions` (splits/dividends) as you encounter them in
   filings or price data.
9. **Anomaly detection (DR-028):** basic sanity checks on ingest — Assets ≈ Liabilities +
   Equity within a small tolerance, no negative values where impossible (e.g. revenue), YoY
   jumps beyond a configurable threshold flagged (not blocked) into `data_quality_issues`.

## Out of scope for this file

No growth/margin/ratio formulas yet — that's Phase 1c, which consumes the clean values this
file produces. No price-based metrics (P/E, market cap) — that needs Phase 1d's price data too.

## Definition of Done

- [ ] `concept_map_v1.yaml` exists and resolves the correct tag for every golden metric on
      NVDA and AAPL
- [ ] `concept_overrides/JPM.yaml` exists and correctly handles JPM's bank-specific tags
- [ ] `fiscal_calendars` correctly reproduces NVIDIA's non-calendar fiscal year end
- [ ] Q4 values for NVDA are correctly derived and flagged `is_derived = true`, with lineage
      to the 4 source facts, and match the golden fixture within rounding tolerance
- [ ] A restated fact test (simulate a 10-K/A) results in two rows, one `is_latest = true`
- [ ] At least one deliberately inconsistent-unit fact ends up in `data_quality_issues`
      instead of being silently stored wrong
