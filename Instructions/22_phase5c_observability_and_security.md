# Phase 5c — Observability & Security Hardening

**Prerequisites:** most of Phase 1–4 exist so there's a real system to instrument and audit.
**Blocks:** `23_phase5d_devops_and_deployment.md` benefits from this being done first (you want
dashboards and security fixes in place before going to production), but the two can overlap.
**Full spec sections:** §28 (observability, error handling, data freshness), §29 (full
security checklist).

## Objective

Instrument the whole system for observability, and run a real security audit against the
checklist in the main spec — fixing what's found, not just documenting it.

## Scope

### Observability

1. **Structured logging (`structlog`, JSON):** every log line includes `request_id`; no
   passwords, tokens, or raw PII logged.
2. **OpenTelemetry tracing:** spans across API → services → retrieval → LLM → citation
   validator, carrying `company`, `intent`, and `prompt_version` as span attributes — this is
   what makes "life of a question" debuggable end to end.
3. **Metrics & dashboards:** API p50/p95/p99 and error rates, queue depth, job failure rate,
   ingestion lag (EDGAR posted → indexed — this should already be logged from Phase 1a's
   `ingestion_runs`, wire it into a dashboard), LLM cost/day, cache hit rate, retrieval score
   distribution, citation rejection rate (from Phase 3a's `claim_verifications`).
4. **Alerting:** ingestion lag > 60 min, job failure spike, LLM spend > budget, repeated SEC
   429s, error-rate SLO burn.
5. **`llm_calls` completeness check:** confirm every LLM call anywhere in the system (report
   generation, chat, news categorization, query rewriting, reranking) logs tokens, cost,
   latency, and prompt version — audit for any call that slipped through without logging.
6. **Data freshness dashboard:** surface `data_freshness` per source per company; confirm the
   fresh/stale/failed states computed here match what the frontend actually displays.
7. **Error-handling audit:** walk through the degradation matrix from spec §28.2 (SEC
   unavailable, news unavailable, AI failure) and confirm each one produces the specified
   user-facing message rather than a generic error or a silent failure.

### Security

8. **Secrets:** confirm `.env.example` has no real values; add secret-scanning
   (gitleaks/trufflehog) to CI; rotate anything found exposed.
9. **Injection surfaces:** confirm ORM/parameterized queries only (grep for raw SQL string
   interpolation); confirm filing/news HTML is sanitized with an allowlist sanitizer before any
   rendering, with CSP headers set.
10. **CORS/CSRF:** explicit origin allowlist; SameSite cookies for the refresh-token flow from
    Phase 4b.
11. **Authorization re-audit:** re-run and expand the IDOR tests from Phase 4b/5a across every
    user-owned resource, including any added since.
12. **Dependency scanning:** pip-audit, npm audit, Dependabot (or equivalent) wired into CI;
    pinned lockfiles; container image scanning if containers are used.
13. **Prompt-injection re-audit:** re-run the red-team corpus from Phase 2c/3c/5a specifically
    against production-shaped inputs (real filing text, real news), not just synthetic test
    strings.
14. **SSRF guard audit:** confirm every outbound fetch (SEC, price, news providers) is
    allowlisted and doesn't follow untrusted redirects.
15. **Encryption & headers:** TLS on managed DB connections, encryption at rest for object
    storage, HSTS/X-Content-Type-Options/frame-ancestors headers set.
16. **Threat model doc (`docs/security.md`):** assets, actors, trust boundaries (specifically:
    untrusted filing/news text flowing into an LLM), and mitigations — write this as a real
    document, not a checklist restated.
17. **Privacy:** confirm account deletion (Phase 4b) actually removes data; confirm user
    question logs have a retention limit; confirm the LLM provider's data-usage settings are
    configured to not train on user data if that option exists.

## Out of scope for this file

Building new features — this file instruments and hardens what already exists. If a security
issue reveals a missing feature (e.g. no rate limiting existed at all), fix the immediate gap
but don't scope-creep into a redesign.

## Definition of Done

- [ ] Every request is traceable end-to-end via `request_id` across logs and traces
- [ ] Dashboards exist for API latency, LLM cost, ingestion lag, cache hit rate, and citation
      rejection rate
- [ ] Alerts fire correctly in a simulated failure (test at least one, e.g. force an ingestion
      lag past the threshold)
- [ ] Every degradation scenario in spec §28.2 produces the specified user-facing message,
      verified by test
- [ ] No secrets in the repo (scanner passes); dependency scan has no unaddressed high/critical
      findings
- [ ] IDOR, injection, CORS/CSRF, and SSRF tests all pass
- [ ] `docs/security.md` exists and accurately describes real trust boundaries and mitigations
- [ ] Account deletion verifiably removes user data
