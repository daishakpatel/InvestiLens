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

> **Phase 0c status:** handlers return schema-shaped examples or `501 Not Implemented`. No real
> business logic yet — that arrives in Phase 4a (endpoints), 4b (auth), 3b/3c (research/chat).

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

### Auth (Phase 4b)
| Method | Path |
|--------|------|
| POST | `/auth/register` |
| POST | `/auth/login` |
| POST | `/auth/refresh` |
| POST | `/auth/logout` |
| GET | `/auth/me` |
| DELETE | `/auth/me` (account + data deletion, LGL-007) |

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

## Regenerating the contract

```bash
make openapi   # writes docs/openapi.json and frontend/src/services/api.d.ts
```
