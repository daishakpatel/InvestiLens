# ADR-0038: Switch the news source on its own with NEWS_PROVIDER

- **Status:** Accepted
- **Date:** 2026-10-19
- **Spec refs:** §21, DR-004, LGL-004

## Problem

The Finnhub client (ADR-0008) was only used with `PROVIDER_MODE=live`, which also switches SEC,
prices, the LLM and embeddings to live. Prices, the LLM and embeddings already have their own
switches (ADR-0035, ADR-0032, ADR-0033), so news was the one source that stayed on sample data in
an otherwise live local setup.

## Decision

`NEWS_PROVIDER=finnhub` selects Finnhub independently of `PROVIDER_MODE`, with the same rules as
`PRICE_PROVIDER`: when it is unset, the mode decides; when Finnhub is selected without
`FINNHUB_API_KEY`, the factory fails loudly instead of falling back to sample news. News rows
don't record their provider, so sample rows already stored (all with `https://news.example/` URLs)
are not removed automatically; they are deleted once by hand when switching.

## Consequences

Real news needs one free key and one setting. The 15-minute news poller makes one Finnhub call
per covered ticker, which fits the free tier's 60 calls/min for a small universe but not for
hundreds of tickers. Storing a provider label on each news row (as on price bars) would let
ingestion clear another provider's rows automatically, and is worth doing if switching becomes
common.
