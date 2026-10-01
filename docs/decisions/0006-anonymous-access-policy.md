# ADR-0006: Anonymous access policy

- **Status:** Accepted
- **Date:** 2026-09-28
- **Spec refs:** §26.1 (AUTH-005), Appendix F item 5, NFR-008

## Problem

Anonymous access lowers the barrier for visitors, which matters for a portfolio project. But
every AI call costs money, and anonymous endpoints are easy to abuse.

## Decision

**Yes to read-only access, no to anonymous AI.** Unauthenticated users MAY:

- search companies and view dashboards (prices, financial metrics, filings list, news headlines)
- view the latest already-generated research report for a company, including citations

Unauthenticated users MAY NOT generate reports, use chat, or access any user-owned resource
(watchlists, saved reports, history). **Anonymous AI quota: 0.** All anonymous endpoints are
rate-limited per IP. User-owned data is never exposed anonymously.

## Consequences

Visitors see the product's output (reports with citations) without signing up, at zero marginal
LLM cost. Any AI spend is tied to an account with an enforced budget (NFR-008). Tradeoff:
visitors can't try chat without registering. We revisit (for example, a small per-IP demo
quota on seed companies) once cost-per-request is measured in production.
