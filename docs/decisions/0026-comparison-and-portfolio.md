# ADR-0026: Company comparison & portfolio analysis (Phase 6a)

- **Status:** Accepted
- **Date:** 2026-10-09
- **Spec refs:** §37.1, §37.2; DR-021, DR-040/041, CIT-001/005, LGL-006, §16.7

## Problem

Phase 6a adds side-by-side company comparison and hypothetical-portfolio analysis. Four decisions
had no prior ADR: (1) how to **calendarize** companies with different fiscal-year ends so NVIDIA's
January FYE is not compared naively against a December-year peer; (2) how to build a **peer set**
when the spec wants SIC/industry + market-cap band but market cap is price-dependent and not yet
persisted (Phase 1d gap); (3) comparison evidence needs globally-unique citation source IDs, but
derived-metric IDs (`derived:<metric>:FY<year>`) collided across companies — a latent bug that also
made `GET /sources` ambiguous; (4) Company profile fields (SIC/sector/FYE) were left NULL by Phase
1a, but peer grouping and sector exposure need them.

## Decision

(1) **Calendarization** maps each fiscal period to the calendar year it predominantly represents: a
period ending in Jan–May belongs to the prior calendar year, Jun–Dec to its own (the common
"calendar year" convention). Base rows use the exact `period_end`; derived rows (no `period_end`)
fall back to `fiscal_year` + the company's FYE month, which agrees with the date-based result.
(2) **Peer set** ranks by SIC proximity (exact code → 3-digit group → 2-digit group → shared
sector), then market-cap proximity *when available*; when market cap is missing the band is skipped
and the degradation is surfaced in `notes`, never silently. (3) Derived-metric `source_id` is now
**company-scoped** (`derived:<TICKER>:<metric>:FY<year>`), fixing cross-company collisions and
`GET /sources` ambiguity; existing citations resolve unchanged via the `financial_metrics.source_id`
lookup. (4) SEC ingestion now **enriches** company metadata (SIC, `sicDescription`→industry,
exchange, FYE) from the `submissions` endpoint; `sector` is derived from SIC via a small
deterministic map (`app/finance/sic.py`). AI comparison commentary reuses the Phase 3a
`citation.verify_text` pipeline verbatim and is withheld entirely if a non-advice guard detects any
buy/sell/hold language (LGL-006). Portfolio metrics (weighted averages, HHI, sector exposure,
volatility/correlation) are all deterministic `Decimal` math; the response returns per-holding data
so the client recomputes what-if weight changes without a round-trip.

## Consequences

Calendarization and percentile ranking work across real fiscal-year mismatches (verified live on
NVDA/AMD/INTC). Peer/market-cap quality improves automatically once Phase 1d persists price-derived
metrics — no code change needed. The source-id scheme change required rebuilding derived metrics
(idempotent) and leaves the analogous `q4_derived:<metric>` quarterly IDs still company-unscoped
(not used by comparison; backlogged). Sector is SIC-derived and coarse (division-level outside the
curated tech/financial ranges); GICS-grade sectors would need a licensed mapping. Portfolio risk
themes depend on completed research reports, so they are empty for companies without one until a
report exists.
