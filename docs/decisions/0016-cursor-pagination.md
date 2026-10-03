# ADR-0016: Opaque keyset cursor pagination

- **Status:** Accepted
- **Date:** 2026-10-02
- **Spec refs:** §24.1, API-002, API-005

## Problem

Every list endpoint needs stable pagination (API-002: `?limit=&cursor=`, responses carry
`next_cursor`), but the Phase 0c contract already froze most list responses as bare JSON arrays
(e.g. `GET /companies/{ticker}/filings` → `list[FilingSummary]`). Phase 4a DoD #6 forbids any
response *shape* from diverging from the published OpenAPI while wiring real logic, so we cannot
wrap those arrays in a `{items, next_cursor}` envelope without a breaking `/v2` change.

## Decision

Pagination is keyset-by-id with an **opaque cursor** = `base64url(str(last_seen_id))`, decoded
defensively (a malformed cursor is a 422, never a crash). Endpoints accept `limit` (default 50,
clamped to [1, 200]) and `cursor`; a query fetches `limit + 1` rows to detect a next page. The
`next_cursor` is returned in the body where the frozen contract already has the field
(`NewsResponse.next_cursor`) and otherwise in an **`X-Next-Cursor` response header**, which keeps
every bare-array response shape byte-identical to the Phase 0c contract. The shared helper lives
in `app/api/pagination.py`.

## Consequences

One uniform, O(limit) pagination path across list endpoints with no offset drift under inserts,
and no breaking contract change. The cost is that bare-array endpoints expose `next_cursor` out of
band (a header) rather than in the body — frontend clients read the header for those. If a future
`/v2` is cut, those endpoints should move to a body envelope for consistency. Keyset assumes an
id-ordered scan; endpoints that order by another column (news by `published_at desc`) still
tie-break on id so the cursor stays monotonic.
