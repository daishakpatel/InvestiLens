# ADR-0035: Prices switch to Tiingo on their own, and a company's history holds one provider

- **Status:** Accepted
- **Date:** 2026-10-13
- **Spec refs:** §7, §11.6, DR-004, DR-025, ING-001, ING-004, LGL-001, SEC-001

## Problem

Prices in the dev database were sample data ending 2026-09-30, because the only way to turn on
Tiingo (ADR-0007) was `PROVIDER_MODE=live`, which also turns on live news and so needs a Finnhub
key. Turning Tiingo on would also have mixed real bars into the sample history: bars are upserted
by date, and the sample set has a bar on every weekday, so made-up bars would survive on market
holidays, along with the sample set's dividends.

## Decision

`PRICE_PROVIDER=tiingo` selects the price source independently of `PROVIDER_MODE`, the same way
`LLM_PROVIDER` (ADR-0032) and `EMBEDDING_PROVIDER` (ADR-0033) do. Each `PriceSource` names its
`provider`, which is stored on every bar. When an ingestion run returns bars, the company's bars
and corporate actions from any other provider are deleted first; a run that returns nothing
changes nothing.

The `price-eod` schedule (ADR-0024) only helps on a machine that is running after the close.
For local use, `REFRESH_PRICES_ON_STARTUP=true` makes the API catch up at start instead: one
background thread re-ingests every active company whose prices were last refreshed more than 12
hours ago, so a restart within that window makes no provider calls. It is off by default, and
stays off wherever Celery Beat runs, because every API instance would otherwise refetch at boot.

## Consequences

Real, current prices need only `TIINGO_API_KEY` and a run of `scripts/ingest_prices.py`. Sample
and real prices can no longer share a chart, and switching back to mock replaces the real data the
same way. ADR-0007's licence note still holds: Tiingo's free plan is for internal use, so a public
deployment must stay on mock prices or move to a plan that permits display.
