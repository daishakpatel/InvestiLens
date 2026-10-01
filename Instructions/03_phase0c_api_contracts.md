# Phase 0c — API Contracts (OpenAPI + Shared Schemas)

**Prerequisites:** `02_phase0b_database_schema.md` done (tables exist to shape response
models against).
**Blocks:** Phase 4a (FastAPI implementation) and Phase 4c/4d (frontend) — both build against
this contract before real logic exists.
**Full spec sections:** §17.2 (ResearchReport schema — copy exactly, don't re-derive), §24
(full API design), §13 (citation schema).

## Objective

Publish the OpenAPI spec and the shared Pydantic schemas *before* any endpoint has real logic
behind it, so the FastAPI and frontend agents can build in parallel against a contract instead
of guessing at each other's shapes.

## Scope

1. **Write the Pydantic schemas** in `backend/app/schemas/` — these are contracts, not
   implementation:
   - `ResearchClaim`, `Risk`, `ManagementTopicStatement`, `Factor`, `NewsItemSummary`,
     `ResearchReport` — copy the model definitions from spec §17.2 exactly (field names,
     types, the rule that `confidence_label`/`internal_confidence`/`change_status` are
     backend-only and the LLM cannot set them).
   - `SourceRecord` (spec §13.3) covering all six `source_type` variants: `text_chunk`,
     `table_chunk`, `xbrl_fact`, `derived_metric`, `news_item`, `earnings_release`/transcript.
   - `MetricResult` (spec §12, DR-040): `value, unit, inputs, formula_id, warnings`.
   - Provider interfaces as abstract base classes (implementations come later):
     `FilingsProvider`, `PriceProvider`, `NewsProvider`, `LLMClient`, `EmbeddingClient`.
2. **Write the OpenAPI spec** (or scaffold FastAPI routers with empty handlers that return
   `501` — either way, the *shape* must be final) for every endpoint in spec §24.2. Group by:
   Health, Company, Financials & Prices, Filings, News, Research (async job pattern), Sources
   (powers the citation modal — don't forget this one, it's easy to miss), Chat, Auth,
   Watchlist/Alerts, Admin.
3. **Apply the conventions from spec §24.1** to every endpoint: RFC 7807 error format,
   cursor-based pagination, `Idempotency-Key` support on `POST /research` and `POST /chat`,
   SSE for job progress and chat streaming, ISO-8601 UTC timestamps, `X-Request-ID` echoed,
   and freshness metadata (`as_of`, `source`, `freshness_status`) on data endpoints.
4. **Fix the one ordering bug from v1**: declare `GET /companies/search` before
   `GET /companies/{ticker}` so the literal path wins.
5. **Generate a TypeScript client** from the OpenAPI spec (e.g. `openapi-typescript`) and
   check it into `frontend/src/services/` (or wire the generation into a Makefile target) so
   the frontend never hand-writes duplicate types.
6. **Contract test**: a CI check that fails if a router's actual response model diverges from
   the published OpenAPI spec.
7. **`docs/api.md`**: human-readable endpoint list (can mostly be the table from spec §24.2 /
   Appendix E) plus the conventions above.

## Out of scope for this file

No real business logic behind any endpoint — every handler can return a hardcoded example
matching its schema, or `501 Not Implemented`. Auth logic itself is Phase 4b.

## Definition of Done

- [ ] All schemas from spec §17.2 and §13.3 exist in `backend/app/schemas/` and validate
- [ ] Every endpoint from spec §24.2 is registered in FastAPI (even if unimplemented) and
      appears in the generated OpenAPI spec
- [ ] `/companies/search` resolves correctly ahead of `/companies/{ticker}` (test this)
- [ ] Error responses use RFC 7807 shape; a shared exception handler enforces it
- [ ] Frontend TypeScript client generates cleanly from the spec with zero manual edits
- [ ] `docs/api.md` published
