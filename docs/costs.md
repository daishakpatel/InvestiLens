# Cost Estimate

Rough monthly cost to run InvestiLens at **demo scale** (a portfolio link: low traffic, 3 seed
companies, anonymous read-only browsing, tightly-capped AI). Hosting is Render (ADR-0023);
figures are list prices as of 2026-10 and **should be re-checked against current pricing** before
relying on them — they are estimates, not quotes.

## Assumptions (demo scale)

- Traffic: < 1 req/s average, bursty; a handful of concurrent visitors.
- Data: NVDA / AAPL / JPM only; daily refresh + pollers.
- Prices/news: `PROVIDER_MODE=mock` (ADR-0007 Tiingo license forbids public display) → **$0**
  for market-data APIs in the demo.
- AI: anonymous visitors can't generate (ADR-0006); registered demo users capped at
  `DEFAULT_AI_BUDGET_MONTH_USD=$0.50`; reports are pre-generated with the deterministic FakeLLM
  (`make seed`), so steady-state LLM spend is ~$0.

## Hosting (Render)

| Service | Plan | Est. $/mo |
|---|---|---|
| API web service | Starter | $7 |
| Worker — interactive | Starter | $7 |
| Worker — ingestion | Starter | $7 |
| Worker — batch | Starter | $7 |
| Beat scheduler | Starter | $7 |
| Postgres 16 (+pgvector) | Basic 256MB | ~$6 |
| Redis (broker/cache/limiter) | Starter | ~$10 |
| Frontend | Static site | $0 |
| **Subtotal** | | **~$58/mo** |

**Cheaper demo variants:**
- Collapse the three workers + beat into **one** worker running all queues (`-Q
  interactive,ingestion,batch`) + a separate beat → ~$14 instead of $28 (saves ~$14/mo). The
  per-queue split matters under load, not at demo scale.
- Render's **free** web tier (spins down when idle) for the API + a single free worker, free
  Postgres (90-day) / free Redis → **~$0/mo**, at the cost of cold starts and the 90-day DB
  expiry. Fine for a résumé link that's visited occasionally.

So the realistic range is **~$0 (all free tiers, cold starts) to ~$58/mo (always-on, split
workers)**. A sensible middle — always-on API + one combined worker + beat + paid DB/Redis — is
**~$30–35/mo**.

## Data & AI providers

| Provider | Demo usage | Est. $/mo |
|---|---|---|
| SEC EDGAR | Filings + XBRL (keyless, public) | $0 |
| Tiingo (prices) | **Not called in demo** (mock; ADR-0007) | $0 |
| Finnhub (news) | **Not called in demo** (mock; ADR-0008) | $0 |
| Voyage (embeddings) | One-time embed of 3 companies' filings, then idle | < $1 (one-off), ~$0 ongoing |
| Anthropic (LLM) | Pre-gen reports via FakeLLM ($0); live only if a key is added + budget raised | ~$0 demo; ~$0.01–0.05 per generated report at `claude-sonnet` rates if enabled |

If the demo were switched to **live** data + real LLM (requires a Tiingo license permitting public
display, and lifting the AI budget cap): budget on the order of **$5–20/mo** for light real
traffic, dominated by LLM report/chat tokens and bounded by the per-user monthly budget
(NFR-008) + the global daily circuit breaker (`llm_daily_budget_usd`, ADR-0022).

## Cost controls already in place

- Per-user monthly AI budget (`ai_budget_month_usd`) → `402` when exceeded (ADR-0022).
- Global daily LLM-spend alert / circuit-breaker signal (`llm_daily_budget_usd`, OBS-003).
- Rate limiting: 100 req/min general, 20 AI req/hour (§25.4).
- Redis cache cuts repeat DB/compute for hot company data (ADR-0024).
- Demo mode: anonymous read-only, AI effectively disabled, reports pre-generated.
