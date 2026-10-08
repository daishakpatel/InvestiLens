# Security

Threat model and mitigations for InvestiLens (spec §29, SEC-001…015). This is a real description
of what the system actually does, not the checklist restated — each claim below was verified
against the code during the Phase 5c audit (see `Instructions/22_phase5c_observability_and_security.md`),
not assumed from the spec.

## 1. Assets

| Asset | Where it lives | Why it matters |
|---|---|---|
| User credentials | `users.password_hash` (Argon2id) | Account takeover |
| Session material | `refresh_tokens.token_hash`, access JWTs (bearer, in-memory on the frontend) | Account takeover, replay |
| Provider API keys (SEC, Tiingo, Finnhub, Voyage, Anthropic) | env only (`app/config.py`), never in code/logs/URLs | Cost abuse, provider ToS violation, key leakage to an attacker who could then pivot to the provider's own account scope |
| User-generated content | `chat_messages`, `watchlists`, `alerts`, `research_reports.user_id` association | Privacy; SEC-007 object-level access |
| Financial data correctness | `financial_facts`, `financial_metrics`, `research_reports` | The product's entire value proposition — a wrong number or a fabricated AI claim is the worst possible failure, not just a bug |
| Infra credentials | `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET` | Full data-plane compromise if leaked |

## 2. Actors

| Actor | Capability | Trust level |
|---|---|---|
| Anonymous visitor | Read-only browsing (companies, filings, financials, prices, news) — no AI, no account (ADR-0006) | Untrusted |
| Registered user | Anonymous capability + chat, research generation, watchlists, alerts, own account deletion | Authenticated, but still capped (per-user AI budget, ADR-0022; rate limits, §25.4) — **not** trusted with another user's data or with unbounded spend |
| Admin (`users.role == "admin"`) | Ingestion-run/eval-run visibility, triggers a company refresh job | Elevated, DB-row-revocable (not a JWT claim — `require_admin` re-reads the row every request, so revoking admin takes effect immediately, not at next token refresh) |
| External data publisher (SEC filer, news outlet) | Controls the *content* of filings/news InvestiLens ingests and feeds to an LLM | **Explicitly untrusted** — see §4 |
| External provider (SEC EDGAR, Tiingo, Finnhub, Voyage, Anthropic) | Receives outbound requests; EDGAR/Tiingo/Finnhub/Voyage responses are parsed and stored | Semi-trusted infrastructure, but still schema-validated on the way in (DR-003) and allowlisted on the way out (SEC-015) |

## 3. Trust boundaries

```text
Browser  ──HTTPS──▶  FastAPI (app/main.py)  ──SQL──▶  Postgres
   ▲                      │        │
   │                 CORS/JWT   outbound (HardenedHttpClient, SEC-015)
   │                      │        ▼
   └──────SSE/JSON────────┘   SEC EDGAR / Tiingo / Finnhub / Voyage / Anthropic
                                      │
                         untrusted filing/news TEXT
                                      ▼
                         LLM prompt (wrap_untrusted, RAG-040)
```

The boundary that matters most for an AI product is **untrusted filing/news text flowing into an
LLM prompt** (the bottom of the diagram). Filing and news text is written by a third party (a SEC
filer, a news outlet) InvestiLens has no control over and must treat as hostile — it is **data to
cite, never instructions to follow** (spec §16.9, RAG-040). Concretely:

- `app/ingestion/documents/clean.py` strips hidden markup (`display:none`, zero-size, etc.)
  before any text reaches a chunk (DP-004) — a hidden instruction never gets the chance to be
  retrieved at all.
- `app/rag/injection.py` wraps every piece of retrieved evidence in explicit untrusted-content
  markers (`wrap_untrusted`) before it enters an LLM prompt, and `neutralize_markers` strips any
  attempt to forge those markers or smuggle control characters from the *source* text itself — an
  attacker who knows the delimiter format cannot escape the sandbox by including it in their own
  text.
- Even if an LLM were persuaded by injected text, **it cannot act**: the only output path is
  Phase 3a's citation verifier (`app/citation/verify.py`), which rejects any claim without a valid
  `source_id`, rejects numeric claims that don't match the cited source, and never lets an LLM's
  claimed citation be trusted at face value. An "obey this injected instruction" response has no
  valid source to cite and is therefore unpublishable as a claim.
- `tests/unit/test_security_corpus.py` and `tests/integration/test_injection_production_shaped.py`
  (added this phase) exercise this against both a synthetic corpus and payloads spliced into a
  **real** SEC filing fixture, run through the real parse → chunk → retrieve → chat pipeline.

## 4. Mitigations (spec §29)

| ID | Mitigation | Where |
|---|---|---|
| SEC-001 | `.env.example` has placeholder values only (never committed real secrets); `.env`/`.env.*` gitignored; CI runs `gitleaks` on every push (`.github/workflows/ci.yml`, `security` job). | `.env.example`, `.gitignore`, CI |
| SEC-002 | Every endpoint's request/response is a Pydantic model; strict response models reject unexpected fields. | `app/schemas/*`, `app/api/*` |
| SEC-003 | ORM/parameterized queries only. The one raw-SQL `text(...)` call (`app/rag/search.py`, `SET LOCAL hnsw.ef_search`) inlines a value that is `int()`-coerced from server config, never user input — audited this phase, no change needed. | `app/rag/search.py:69` |
| SEC-004 | The frontend never renders filing/news content as HTML — only as plain chunked text (`document_chunks.text`), so there is no HTML to sanitize. `frontend/src/lib/xssGuard.test.ts` fails the build if `dangerouslySetInnerHTML` is ever introduced. CSP (`default-src 'none'`) + `X-Content-Type-Options`/`X-Frame-Options` headers on every API response (added this phase, `app/api/security_headers.py`). | `app/api/security_headers.py`, `frontend/src/lib/xssGuard.test.ts` |
| SEC-005 | Explicit CORS origin allowlist (`cors_allowed_origins`, no `"*"`), added this phase (`app/main.py`). | `app/main.py`, `app/config.py`, `tests/unit/test_cors.py` |
| SEC-006 | Refresh-token cookie is `httpOnly` + `Secure` + `SameSite=Strict`, scoped to `/api/v1/auth`. `Strict` plus a non-browser-form JSON API is judged sufficient without a separate CSRF token (ADR-0005/0006). | `app/auth/service.py`, `app/config.py` |
| SEC-007 | Object-level ownership checks on every user-owned resource (watchlists, alerts, chat sessions); admin endpoints role-gated. Re-audited and expanded this phase — added a cross-user isolation test for `/alerts` (previously only watchlists/chat sessions were IDOR-tested). Research reports are intentionally public-readable by design (ADR-0006) — `user_id` is a "my reports" association, not an access gate. | `tests/integration/test_api_endpoints.py::test_alert_and_watchlist_lists_are_user_scoped`, `tests/integration/test_auth.py::test_idor_watchlist_and_chat_session` |
| SEC-008 | Rate limiting (100 req/min general, 20 AI req/hour, both per-user when authenticated) + per-user monthly AI budget (`users.ai_budget_month_usd`, enforced this phase) + a global daily-spend alert as a circuit-breaker signal. Off by default; `rate_limit_backend="redis"` for a real multi-worker deployment. | `app/api/middleware.py`, `app/billing/budget.py`, ADR-0022 |
| SEC-009 | `pip-audit --strict` (backend) and `npm audit --omit=dev --audit-level=high` (frontend) in CI; `uv.lock`/`package-lock.json` pinned; Dependabot weekly for pip/npm/GitHub Actions. | `.github/workflows/ci.yml`, `.github/dependabot.yml` |
| SEC-010 | See §3 above (RAG-040). Output URL allowlisting: the frontend only ever links to a source's own `deep_link` (resolved server-side from a known scheme — SEC EDGAR, a stored news URL), never a raw LLM-generated URL. | `app/citation/resolver.py` |
| SEC-011 | Managed Postgres connections use `sslmode=require` in any shared/production `DATABASE_URL` (not enforced locally — local Postgres has no TLS listener). Object storage is filesystem for the MVP (ADR-0012); S3 encryption-at-rest is a Phase 5d deployment configuration, not a code change, once the backend swaps. | deployment config (not yet deployed, §31.3) |
| SEC-012 | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy`, `Referrer-Policy` on every response; HSTS gated behind `hsts_enabled` (only meaningful once TLS actually terminates — sending it over plain HTTP is a no-op/footgun). CSP is exempted on `/docs`/`/redoc` only — a strict `default-src 'none'` silently breaks FastAPI's CDN-loaded interactive docs in a real browser; every actual API response keeps it. Added this phase. | `app/api/security_headers.py`, `tests/unit/test_security_headers.py` |
| SEC-013 | This document. | — |
| SEC-014 | Account deletion (`DELETE /auth/me`) soft-deletes immediately and revokes all refresh-token families; `hard_delete_user` (verified this phase to cascade to `chat_sessions`/`watchlists`/`alerts`/`refresh_tokens`/`auth_tokens`, and to null `research_reports.user_id`/`jobs.created_by` rather than deleting public reports) is the retention-job path (Celery wiring is Phase 5d). `chat_message_retention_days` config + `scripts/purge_chat_history.py` (added this phase) give question-log retention a real limit. LLM provider data-usage settings (e.g. Anthropic's "don't train on my data") are an account-level dashboard setting, not code — flagged as a manual pre-launch checklist item since no live key exists yet (ADR-0009). | `app/auth/service.py`, `scripts/purge_chat_history.py`, `tests/integration/test_auth.py` |
| SEC-015 | Every outbound call goes through `HardenedHttpClient`, which checks the target host against a per-provider allowlist (`www.sec.gov`/`data.sec.gov`/`sec.gov`, `api.tiingo.com`, `finnhub.io`, `api.voyageai.com`) and sets `follow_redirects=False` — a redirect to an attacker-controlled host is never followed. Audited this phase: grepped for any `httpx`/`requests` usage outside this client — none found. | `app/utils/http.py`, `app/providers/*/live.py` |

## 5. What's explicitly not done (and why)

- **No WAF / DDoS protection** — out of scope for a portfolio-sized deployment (§31.3); a real
  deployment would sit behind Cloudflare/the hosting provider's edge, which is a deployment
  decision (Phase 5d), not an application-code concern.
- **No CSRF token issuance** — judged unnecessary given `SameSite=Strict` + JSON-only API (SEC-006
  above); revisit if a browser-form (non-fetch) flow is ever added.
- **No WebAuthn/MFA** — not in the MVP spec; email+password with Argon2id is the stated baseline
  (ADR-0005).
- **No live penetration test** — this document and its linked tests are a self-audit, not an
  independent red-team engagement.
