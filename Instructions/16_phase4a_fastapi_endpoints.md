# Phase 4a — FastAPI Endpoints (Real Implementation)

**Prerequisites:** `03_phase0c_api_contracts.md` (contract exists), and ideally most of Phase
1–3 done so endpoints have real logic to call — but routers can be filled in incrementally as
each backing system lands. At minimum, `17_phase4b_auth_and_users.md` should land around the
same time since several endpoints require auth.
**Blocks:** `18_phase4c_frontend_dashboard.md` and `19_phase4d_frontend_report_and_chat.md`
(nothing real to call without this).
**Full spec sections:** §24 (full API design — this file replaces every `501` stub from Phase
0c with real logic).

## Objective

Wire every endpoint from the Phase 0c contract to its real backing service: Company/Financials
to Phase 1, Filings/News to Phase 1a/1e, Research/Sources to Phase 3, Chat to Phase 3c.

## Scope

1. **Company:** `GET /companies/search`, `GET /companies/{ticker}` — real lookups against
   `companies`/`company_identifiers` (Phase 1a), with the route-ordering fix already in place
   from Phase 0c.
2. **Financials & prices:** `GET /companies/{ticker}/financials`,
   `/metrics/{metric_name}/lineage`, `/valuation`, `/prices` — read from `financial_metrics`
   (Phase 1c) and `price_history` (Phase 1d); the `lineage` endpoint surfaces a
   `MetricResult`'s `inputs` chain for the frontend's "how was this calculated" view.
3. **Filings:** `GET /companies/{ticker}/filings`, `GET /filings/{id}`,
   `/filings/{id}/sections` — read from `filings`/`document_chunks` (Phase 1a/2a). Leave
   `/filings/{id}/diff` as a documented stub if filing-diff (Phase 6b) hasn't landed yet.
4. **News:** `GET /companies/{ticker}/news` with category/date/source/relevance filters —
   reads from Phase 1e's `news` table.
5. **Research (async job pattern):** `POST /research` creates a job and returns `202` with
   `research_id`/`job_id`; `GET /research/jobs/{job_id}` and `/events` (SSE) report progress;
   `GET /research/{research_id}` and `/companies/{ticker}/research/latest` return the completed
   report from Phase 3b. Implement `Idempotency-Key` support here specifically — a duplicate
   `POST /research` for the same company/`data_version` should attach to the already-running
   job (single-flight), not start a second one.
6. **Sources:** confirm `GET /sources/{source_id}` (built in Phase 3a) is correctly wired
   through the router layer with proper error handling for unknown IDs.
7. **Chat:** `POST /chat`, `POST /chat/stream`, `GET /chat/sessions/{id}`,
   `POST /chat/messages/{id}/feedback` — wire to Phase 3c.
8. **Watchlist/alerts:** basic CRUD against `watchlists`/`watchlist_items`/`alerts` — the
   actual alert *dispatch* logic (checking for new filings, sending notifications) belongs to
   background jobs (Phase 5d), this file just needs the CRUD API.
9. **Admin:** `GET /admin/ingestion-runs`, `/admin/eval-runs`, `POST
   /admin/companies/{ticker}/refresh` — role-gated (depends on Phase 4b's auth roles).
10. **Cross-cutting, apply to every endpoint (spec §24.1):**
    - RFC 7807 error responses via a shared exception handler
    - Cursor-based pagination on every list endpoint
    - `X-Request-ID` generated/echoed and threaded into logs
    - Freshness metadata (`as_of`, `source`, `freshness_status`) on data endpoints, sourced
      from `data_freshness` (Phase 1a/1d/1e populate this)
    - Rate limiting middleware hooks (full limits configured in Phase 5c, but the middleware
      layer should exist here)

## Out of scope for this file

No new business logic beyond wiring — if a section's underlying data doesn't exist yet
(e.g. filing diff), return a clear "not yet available" response rather than faking data. Auth
enforcement itself is Phase 4b; this file assumes auth dependencies exist and applies them.

## Definition of Done

- [ ] Every endpoint from the Phase 0c OpenAPI spec returns real data against the seed
      companies (or a clear "not available" response for features not yet built)
- [ ] `POST /research` correctly single-flights duplicate concurrent requests for the same
      company via `Idempotency-Key`
- [ ] Every list endpoint paginates correctly with cursors
- [ ] A deliberately-triggered error returns a proper RFC 7807 response, not a raw stack trace
- [ ] `X-Request-ID` appears in logs end-to-end for a single request across service calls
- [ ] Contract tests from Phase 0c still pass — no endpoint's actual response shape diverged
      from the published OpenAPI spec while wiring in real logic
