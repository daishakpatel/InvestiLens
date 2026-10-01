# ADR-0008: News provider — Finnhub (free tier)

- **Status:** Accepted
- **Date:** 2026-09-28
- **Spec refs:** §7, §10.8, LGL-004, NFR-006, Appendix F item 1

## Problem

We need recent company news (headline, publisher, timestamp, URL, short summary) for US
companies. The budget is $0 for MVP, and we can't republish full articles (LGL-004).

## Decision

Use **Finnhub** `company-news` behind `NewsProvider`. Free tier (checked 2026-09-28): **60
calls/minute** (with a 30 calls/second burst cap), **1 year of company-news history**, North
American companies only. We store only headline, URL, publisher, `published_at`, and Finnhub's
summary. No full article text.

## Consequences

Headline-level news fits the MVP's US-only scope, and the rate limit easily covers on-request
refresh of 10 seed companies (news no more than 15 minutes old, NFR-006) with caching. News is
a lower-tier source in the source hierarchy (§15), so claims needing depth must come from
filings. Fallback: Tiingo's news API (3 months of history on its free tier) can be added behind
the same interface. Terms of use are re-checked before public deployment, as for ADR-0007.
