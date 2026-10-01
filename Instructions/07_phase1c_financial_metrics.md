# Phase 1c — Financial Metrics (Deterministic Calculations)

**Prerequisites:** `06_phase1b_xbrl_concept_map.md` done — clean, canonical
`financial_facts`/period values must exist.
**Blocks:** `14_phase3b_research_report_generation.md` (the report's numeric panels come
straight from here), `18_phase4c_frontend_dashboard.md` (charts read `financial_metrics`).
**Full spec sections:** §12 (full metric catalog with every formula — this file implements
it), Appendix C (sector applicability), DR-040…043.

## Objective

Write the deterministic Python formulas that turn clean facts into every ratio, margin, and
growth figure the dashboard and reports show. **No LLM involvement anywhere in this file.**

## Scope

1. **Build `backend/app/finance/metrics.py`** as pure functions — no I/O, no database calls
   inside the formulas themselves (they take numbers in, return a `MetricResult` out). Copy
   every formula from spec §12's table exactly:
   - Growth & aggregate: YoY growth, CAGR, TTM series
   - Profitability: gross/operating/net margin, EBITDA (with the DR-010 reliability rule —
     only compute if operating income *and* D&A both exist for the same filing, otherwise
     `None` with reason `MISSING_INPUT`), FCF, FCF margin, FCF conversion
   - Balance sheet: total debt, net cash, cash/debt, current ratio, quick ratio, debt/equity
   - Valuation: market cap, enterprise value, P/E, P/S, P/FCF, EV/Revenue, EV/EBITDA, FCF yield
   - Efficiency: DSO, DIO, DPO, cash conversion cycle, accruals ratio, SBC % revenue,
     dilution, capex intensity
   - Returns & quality: ROE, ROA, ROIC, Piotroski F-score, Altman Z-score
   - `percentile_rank` utility for later valuation-band and peer features
2. **`MetricResult` contract (DR-040):** every function returns
   `MetricResult(value, unit, inputs, formula_id, warnings)` — the `inputs` list is what later
   powers citation lineage for derived numbers (Phase 3a depends on this shape).
3. **Never divide by a zero/negative denominator silently (DR-041):** return `None` with a
   reason code (`NEGATIVE_BASE`, `MISSING_INPUT`, `NOT_APPLICABLE_SECTOR`) instead of raising or
   returning garbage.
4. **Sector applicability (DR-042):** build `sector_applicability.yaml` (spec Appendix C) as
   data, not `if sector == "bank"` branches scattered through the code. A metric's applicability
   is looked up, not hardcoded. Verify against JPM: gross margin, current ratio, EV/EBITDA, and
   Piotroski/Altman should all resolve to "Not applicable," never to zero or a nonsense number.
5. **Formula versioning (DR-043):** every formula has a `formula_id` + version; changing a
   definition later bumps the version rather than silently changing historical numbers.
6. **Persist computed values** into `financial_metrics` (from Phase 0b's schema) with
   `metric_name`, `period`, `is_derived`, `formula_id`, `source_id` — this table is what every
   other layer reads from; nothing downstream should re-derive metrics itself.
7. **Property-based tests (Hypothesis):** growth/CAGR invariants (e.g. CAGR of a flat series is
   0), unit-conversion round-trips, and the "never divide by zero" rule, across randomized
   inputs.
8. **Exact-match tests against `golden_metrics.json`** for NVDA, AAPL, and JPM — this is a hard
   gate, not a nice-to-have.

## Out of scope for this file

No price-dependent computation until Phase 1d's price data exists (P/E, market cap, EV can be
stubbed/tested with fixture prices from Phase 0d in the meantime). No peer/percentile
comparisons against *other* companies yet (Phase 6).

## Definition of Done

- [ ] `finance/metrics.py` implements every formula in spec §12's table as a pure function
- [ ] 100% test coverage on `finance/` (this module is the one place the spec asks for full
      coverage, not just 80%)
- [ ] Golden-fixture exact-match tests pass for NVDA, AAPL, and JPM
- [ ] JPM correctly shows "Not applicable" (not zero, not null-without-reason) for
      sector-inapplicable metrics
- [ ] Every `MetricResult` includes traceable `inputs` — verified by a test that walks a
      derived metric back to its underlying facts
- [ ] No `Float` used anywhere in the calculation path; no bare division without a guard
