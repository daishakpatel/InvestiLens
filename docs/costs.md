# Cost Estimate

Rough monthly cost to run Assay Desk at **demo scale** (a portfolio link: low traffic, 3 seed
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

> **Current demo blueprint (Phase 7l, ADR-0050): about $30/mo.** `render.yaml` now runs the
> trimmed shape: Starter API $7, one Starter worker with Beat in-process $7, Postgres Basic-256MB
> about $6, Redis Starter about $10, static frontend $0. It uses no model or data-provider keys,
> so provider spend is $0. The table below is the original five-service layout, kept for the
> case where the demo outgrows one worker.

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
| Finnhub (news) | Free tier when `NEWS_PROVIDER=finnhub` (ADR-0038); otherwise sample news (ADR-0008) | $0 on the free tier (60 calls/min) |
| Embeddings: Gemini `gemini-embedding-2` (ADR-0033) or Voyage (ADR-0010) | One-time embed of the ingested filings, then one request per question | $0 on Gemini's free tier, capped at 100 texts a minute and 1,000 a day (eight days for the dev DB's 7,722 chunks); paid Gemini is $0.20 per 1M tokens, about $0.35 once for that corpus; Voyage < $1 one-off |
| Gemini (LLM, ADR-0032) | Free tier when `LLM_PROVIDER=gemini`; otherwise pre-generated FakeLLM reports | $0 on the free tier. Free tier is capped at 20 requests/day on `gemini-3.8-flash` (about one report). Paid tier, measured 2026-10-12 on one NVDA run: about $0.05 per report (47k input / 5k output tokens over 12 calls), under $0.01 per chat answer |

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
