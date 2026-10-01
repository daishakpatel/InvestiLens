# Phase 4b — Authentication & User Features

**Prerequisites:** `02_phase0b_database_schema.md` done (`users`, `refresh_tokens`,
`watchlists`, `alerts` tables exist). Can run in parallel with Phase 1–3.
**Blocks:** any endpoint in `16_phase4a_fastapi_endpoints.md` that requires auth (watchlist,
saved reports, chat history, admin).
**Full spec sections:** §26 (full auth & user features spec), §29/SEC-001…015 for the security
requirements that overlap with auth specifically.

## Objective

Build real registration, login, JWT issuance/rotation, and the user-facing features
(watchlist, saved reports, alerts) that depend on having a real user.

## Scope

1. **Password handling (AUTH-001):** Argon2id hashing; a basic password policy (length
   minimum, no other cleverness needed for a portfolio project); no plaintext ever logged.
2. **Registration & login:** `POST /auth/register`, `POST /auth/login` — issue a short-lived
   access token (15 min) and a rotating refresh token (7–30 days) per AUTH-002. Store refresh
   tokens **hashed**, never plaintext, in `refresh_tokens`. Detect refresh-token reuse
   (a sign of theft) and revoke the whole token family if it happens.
3. **Cookie strategy:** refresh token in an httpOnly, Secure, SameSite cookie; access token
   returned in the response body for the frontend to hold in memory (not localStorage).
4. **Email verification & password reset (AUTH-003):** rate-limited, single-use tokens; don't
   over-build this — a working minimal flow is enough.
5. **Protected routes & object-level authorization (AUTH-004):** every user-owned resource
   (watchlist, saved report, chat session) must check that the requesting user actually owns
   it — write an explicit IDOR test (user A cannot fetch user B's watchlist by guessing an ID).
6. **Anonymous access (AUTH-005):** implement whatever was decided in ADR-0006 from Phase 0a —
   either read-only company browsing with no/limited AI quota, or full auth-required. Don't
   leave this ambiguous in code.
7. **Rate limiting on auth endpoints (AUTH-006):** login attempts rate-limited/backed off
   per account and per IP.
8. **Account deletion:** `DELETE /auth/me` — soft-delete user data with a hard-delete job path
   for actual removal (ties into LGL-007's retention requirement), since this is a "not
   investment advice" consumer product and users may reasonably want their data gone.
9. **Watchlist:** CRUD on `watchlists`/`watchlist_items`.
10. **Alerts:** CRUD on `alerts` (`new_10k|new_10q|new_8k|price_move|news_category`, channel
    `email|in_app`) — the actual trigger/dispatch logic lives in Phase 5d's background jobs;
    this file just needs the config API and data model working correctly.
11. **Saved reports & chat history:** confirm `research_reports`/`chat_sessions` correctly
    associate to `user_id` when a logged-in user generates a report or starts a chat, so
    "research history" works without extra plumbing.
12. **Per-user AI budget (NFR-008):** `users.ai_budget_month_usd` enforced — once Phase 5c's
    cost tracking exists, this file's job is to make sure the budget check actually blocks
    further AI calls with a clear message, not just log a warning.

## Out of scope for this file

Google/GitHub OAuth (explicitly "later" in the spec, don't build it for MVP). Alert dispatch
logic itself (Phase 5d). Full security audit (Phase 5c) — this file implements the auth
requirements, Phase 5c later verifies them adversarially.

## Definition of Done

- [ ] Registration, login, token refresh, and logout all work end-to-end
- [ ] Refresh tokens are stored hashed; a simulated reuse-after-rotation attempt revokes the
      token family
- [ ] A user cannot access another user's watchlist, saved report, or chat session by ID
      (explicit IDOR test passes)
- [ ] Anonymous access behaves exactly as ADR-0006 specifies — no undefined in-between state
- [ ] Login is rate-limited; repeated failed attempts are throttled
- [ ] `DELETE /auth/me` removes/soft-deletes the user's data
- [ ] Watchlist and alert CRUD work and are correctly scoped to the authenticated user
