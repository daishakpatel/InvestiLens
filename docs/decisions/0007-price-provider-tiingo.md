# ADR-0007: Price provider — Tiingo (free Starter tier)

- **Status:** Accepted
- **Date:** 2026-09-28
- **Spec refs:** §7, §11.6 (DR-025), LGL-003, Appendix F item 1

## Problem

We need daily end-of-day (EOD) prices, volume, split- and dividend-adjusted history, and
corporate actions for US equities. The budget is $0 for MVP.

## Decision

Use **Tiingo** behind `PriceProvider`. Free Starter tier limits (checked 2026-09-28): **50
requests/hour, 1,000 requests/day, 500 unique symbols/month**, 30+ years of EOD history, with
adjusted prices and split/dividend data. **License: internal/personal use only.** The data may
not be displayed or shared with others.

## Consequences

Enough for development and the 10-company seed set: a full-history backfill is about one
request per symbol, and daily refresh is about 10 requests. Responses are cached and refreshed
once per trading day. **Blocking item before any public deployment:** the free license doesn't
allow showing prices to other users (LGL-003). Before launch we either move to a paid Tiingo
plan that allows display or swap providers behind `PriceProvider` (Polygon, Financial Modeling
Prep). Provider terms are re-checked at that point.
