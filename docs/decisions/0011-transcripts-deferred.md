# ADR-0011: Earnings-call transcripts deferred to Phase 2

- **Status:** Accepted
- **Date:** 2026-09-28
- **Spec refs:** §4.1, §7, LGL-005, Appendix F item 2

## Problem

Earnings-call transcripts are valuable for management commentary, but they are almost always
licensed content. No free source permits storing and quoting them, and scraping them violates
LGL-005.

## Decision

**Transcripts are out of MVP scope.** Management commentary (§10.11) comes from 8-K Exhibit
99.1 earnings releases and 10-K/10-Q MD&A, both public SEC filings. No `TranscriptProvider` is
built in MVP. The `transcript` source type stays in the citation schema (§13.3), so adding it
later isn't a breaking contract change.

## Consequences

No licensing risk or extra cost in MVP. Management commentary loses Q&A-session nuance. We
revisit in Phase 2 if a licensed transcript provider fits the budget.
