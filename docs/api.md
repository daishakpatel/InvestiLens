# API

FastAPI, OpenAPI 3.1, versioned under `/api/v1` (spec §24). This is the human-readable map;
the machine contract is [`openapi.json`](openapi.json), generated from the app and consumed by
the frontend as a typed client (`frontend/src/services/api.d.ts`).

> **Contract-first.** Routes and Pydantic schemas are the source of truth. Regenerate the spec
> and client with `make openapi` after any change; a CI contract test fails if `openapi.json`
> drifts from the app. Additive changes only within `/v1`; breaking changes go to `/v2`
> (API-005) and require an ADR.

## Conventions (§24.1)

| ID | Convention |
|----|-----------|
| API-001 | Errors are RFC 7807 `application/problem+json` (`type`, `title`, `status`, `detail`, `instance`, `request_id`, optional `errors[]`), enforced by a shared handler. |
| API-002 | Cursor pagination (`?limit=&cursor=`); responses carry `next_cursor`. |
| API-003 | `Idempotency-Key` header honoured on `POST /research` and `POST /chat`. |
| API-004 | Server-Sent Events for job progress and chat streaming (`text/event-stream`). |
| API-005 | Additive-only within `/v1`; breaking changes → `/v2`. |
| API-006 | ISO-8601 UTC timestamps; monetary responses declare `unit`. |
| API-007 | `X-Request-ID` is accepted, echoed on the response, and included in error bodies. |
| API-008 | Data endpoints return freshness (`as_of`, `source`, `freshness_status`). |

> **Phase 4a status:** endpoints are wired to their real backing stores (companies/financials →
> Phase 1, filings/news → 1a/1e, research/sources → Phase 3, chat → 3c). Features whose data is
> not yet ingested return a clear empty/`404`/`501` (insiders/ownership P2, filing & research diff
> Phase 6, export Phase 4d) rather than faked data. Auth is implemented in Phase 4b (see below).

### Cross-cutting (Phase 4a)

- **Pagination (API-002, ADR-0016):** list endpoints accept `?limit=` (default 50, max 200) and an
  opaque `?cursor=`. `GET /companies/{ticker}/news` carries `next_cursor` in the body; the other
  list endpoints (bare arrays, whose contract shape is frozen) return it in an `X-Next-Cursor`
  response header. A malformed cursor is a 422 problem.
- **Idempotency (API-003, ADR-0017):** `POST /research` single-flights — a repeat with the same
  `Idempotency-Key`, or any in-flight job for the same company, attaches to the existing job
  instead of starting a second one. The job is enqueued (`queued`); the Phase 5d worker runs it.
- **Freshness (API-008):** data endpoints read `data_freshness` for their source (`sec`/`price`/
  `news`) and report `as_of`/`source`/`freshness_status` (`stale` when never ingested).
- **Rate limiting (ADR-0018/0022):** `RateLimitMiddleware` is disabled by default
  (`rate_limit_enabled`); when on, a general `429` tier (default 100/min, spec §25.4) applies to
  every route and a tighter AI tier (default 20/hour) applies to `/chat*` and `POST /research`,
  keyed per-user when authenticated else per-IP. Backend is `"memory"` (default, in-process) or
  `"redis"` (real cross-worker limiting via `REDIS_URL`). Responses carry `Retry-After`.
- **AI budget (NFR-008, ADR-0022):** `POST /chat` (qualitative answers only) and `POST /research`
  return `402` (`application/problem+json`) once a user's monthly AI spend reaches their
  `ai_budget_month_usd` cap (set at registration; `default_ai_budget_month_usd` in config).
- **Auth (ADR-0005/0006):** chat, watchlists, and alerts require a user via a Bearer JWT; admin
  endpoints additionally require `role=admin`.
- **Observability (ADR-0021):** `GET /metrics` (root-level, not under `/api/v1` — it's a scrape
  endpoint, not a business API) exposes Prometheus metrics; see `docs/observability.md`.

## Endpoints (§24.2)

### Health & meta
| Method | Path | Notes |
|--------|------|-------|
| GET | `/health` | Liveness |
| GET | `/ready` | Readiness (db, redis, queue) |
| GET | `/meta/data-freshness/{ticker}` | Per-source freshness |

### Company
| Method | Path | Notes |
|--------|------|-------|
| GET | `/companies/search?q=` | Fuzzy search (FR-001). **Declared before `/{ticker}`.** |
| GET | `/companies/{ticker}` | Company profile + freshness |

### Financials & prices
| Method | Path | Notes |
|--------|------|-------|
| GET | `/companies/{ticker}/financials?metrics=&period_type=&from=&to=` | Metric series |
| GET | `/companies/{ticker}/metrics/{metric_name}/lineage?period=` | Derivation lineage (CIT-003) |
| GET | `/companies/{ticker}/valuation` | Valuation metrics |
| GET | `/companies/{ticker}/prices?start=&end=&interval=` | OHLCV |
| GET | `/companies/{ticker}/insiders` | Form 4 (P2) |
| GET | `/companies/{ticker}/ownership` | 13F (P2) |

### Filings
| Method | Path | Notes |
|--------|------|-------|
| GET | `/companies/{ticker}/filings?type=&limit=&cursor=` | Filing list |
| GET | `/filings/{filing_id}` | Filing detail |
| GET | `/filings/{filing_id}/sections` | Section outline |
| GET | `/filings/{filing_id}/diff?against=` | Filing diff (P2, 501) |

### News
| Method | Path | Notes |
|--------|------|-------|
| GET | `/companies/{ticker}/news?category=&from=&to=&source=&min_relevance=` | Headlines (LGL-004) |

### Research (async job pattern, §25.1)
| Method | Path | Notes |
|--------|------|-------|
| POST | `/research` | 202 + `job_id`; `Idempotency-Key` (API-003) |
| GET | `/research/jobs/{job_id}` | Poll job state |
| GET | `/research/jobs/{job_id}/events` | SSE progress (API-004) |
| GET | `/research/{research_id}` | Completed report |
| GET | `/companies/{ticker}/research/latest` | Latest report |
| GET | `/research/{research_id}/diff?against=` | Report diff (P2, 501) |
| GET | `/research/{research_id}/export?format=pdf\|md` | Export (Phase 4d, 501) |

### Sources (citation modal)
| Method | Path | Notes |
|--------|------|-------|
| GET | `/sources/{source_id}` | Source record + span + deep link (CIT-006) |

### Chat
| Method | Path | Notes |
|--------|------|-------|
| POST | `/chat` | Non-streaming answer + citations |
| POST | `/chat/stream` | SSE token stream (API-004) |
| GET | `/chat/sessions/{id}` | Session history |
| POST | `/chat/messages/{id}/feedback` | Thumbs up/down |

Chat requires an authenticated user (ADR-0006: no anonymous AI). Phase 3c resolves the user from an
`X-User-Id` header as an interim seam; Phase 4b replaces it with JWT verification without changing
call sites. The answer is retrieval-routed (structured metrics vs documents), citation-verified
(Phase 3a), and returns `evidence_label`, `abstained`/`refused`, `tool_trace`, `suggested_questions`,
and `message_id` (for feedback).

### Auth (Phase 4b — implemented, ADR-0005/0006)
| Method | Path | Notes |
|--------|------|-------|
| POST | `/auth/register` | Argon2id hash, password policy (AUTH-001); 201 → profile |
| POST | `/auth/login` | Access JWT in body + rotating refresh token in httpOnly/Secure/SameSite cookie; rate-limited (AUTH-006) |
| POST | `/auth/refresh` | Rotates the refresh cookie; reuse of a revoked token revokes the family (AUTH-002) |
| POST | `/auth/logout` | Revokes the token family and clears the cookie |
| GET | `/auth/me` | Current profile (Bearer access token) |
| DELETE | `/auth/me` | Soft-deletes the account + revokes sessions; hard-delete via a retention job (LGL-007) |
| POST | `/auth/verify-email/request` · `/auth/verify-email/confirm` | Single-use email-verification token (AUTH-003) |
| POST | `/auth/password-reset/request` · `/auth/password-reset/confirm` | Single-use reset token; neutral ack (no user enumeration) |

Access tokens are HS256 JWTs (15 min, claims `sub`/`exp`/`iat`/`jti`) sent as `Authorization:
Bearer`; the frontend holds them in memory. Protected routes resolve the user from the verified
token (`get_current_user`), replacing Phase 3c/4a's interim `X-User-Id` seam with no call-site
change. Object-level authorization (SEC-007/AUTH-004) scopes every user-owned resource to the
caller. Per ADR-0006, anonymous users may browse company data and view already-generated reports,
but **may not** generate reports, use chat, or touch user-owned data (anonymous AI quota 0).

### Watchlist, alerts & feedback
| Method | Path |
|--------|------|
| GET / POST | `/watchlists`, `/watchlists/{id}` (DELETE) |
| GET / POST | `/alerts`, `/alerts/{id}` (DELETE) |
| POST | `/feedback/report` |

### Admin (internal)
| Method | Path |
|--------|------|
| GET | `/admin/ingestion-runs` |
| GET | `/admin/eval-runs` |
| POST | `/admin/companies/{ticker}/refresh` |

### Comparison & portfolio (Phase 6a, §37.1/§37.2)
| Method | Path | Notes |
|--------|------|-------|
| GET | `/compare?tickers=NVDA,AMD,INTC&metrics=…&period=…` | Deterministic side-by-side: calendarized (aligned fiscal periods, DR-021), sector-normalized percentiles. Public. 2–6 tickers; `metrics`/`period` optional (default set; latest common calendar year). |
| GET | `/compare/peers/{ticker}` | Peer-set suggestions by SIC/industry + market-cap band. Public. |
| POST | `/compare/commentary` | AI commentary on the differences — cited + verified by the Phase 3a pipeline, non-advisory (LGL-006). Requires auth + AI budget (like research/chat). |
| POST | `/portfolio/analyze` | Analyze a hypothetical portfolio (ticker + weight). Deterministic weighted metrics, HHI concentration, sector exposure, price-based volatility/correlation, and aggregated **cited** risk themes. Public (no LLM generation). Returns `holdings_data` so the client recomputes what-if weight changes with no round-trip. |

Every comparison/portfolio response carries a `disclaimer`: analysis only, never a buy/sell/hold
recommendation. The `compare_companies(tickers, metrics, period)` read-only tool (§16.7) exposes the
same deterministic comparison to the agent layer. Calendarization and the company-scoped derived
`source_id` scheme are ADR-0026.

## Regenerating the contract

```bash
make openapi   # writes docs/openapi.json and frontend/src/services/api.d.ts
```
