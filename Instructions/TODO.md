# InvestiLens — Remaining Work

Audit date: 2026-10-12. All 25 task files and the 5 `UI_plan/` steps have been worked through;
this is what is still open against `docs/InvestiLens_Spec_v2.md`.

Tags: `[code]` = re-checked in the code/CI on the audit date. `[notes]` = carried from earlier
session hand-offs, not re-checked.

## 0. Broken right now

- [ ] **CI is red on `develop`** (last 4 pushes) — fixed locally 2026-10-12, not yet pushed.
      `test_search_resolves_before_ticker` needed a seeded dev database; it now checks routing
      offline. Tick this once a push shows CI green, including the image build. `[code]`
- [ ] `GET /companies/{ticker}/research/latest` returns 500 when the stored report fails validation
      (`ResearchReport.model_validate` is unguarded, `backend/app/api/companies.py:465`). `[code]`
- [ ] Filings list pages by `id desc`, not filing date (`backend/app/repositories/filings.py:30`);
      the Filings tab works around it by fetching 200 and sorting. `[code]`
- [ ] INTC 10-K/10-Q parse to 0 chunks. `[notes]`
- [ ] 10-Q Part I (financial statements + MD&A) is dropped by section detection, so language
      tracking and diffs miss 10-Q MD&A. Needs a `parser_version` bump. `[notes]`

## 1. MVP Definition of Done (spec §36) — not yet met

- [x] **Live LLM client** — Gemini behind `LLMClient` (`backend/app/providers/gemini.py`,
      ADR-0032). Verified live 2026-10-12: a cited chat answer and a six-section NVDA report.
- [ ] **Free tier allows 20 requests a day on `gemini-3.8-flash`; one report uses 10–14.**
      Decide: enable billing (measured about $0.05 per report, under $0.01 per chat answer), or
      point `LLM_MODEL_STRONG` at a model with a higher free limit. `[code]`
- [x] **Chat declined every question** — fixed 2026-10-12: keyword search now falls back to
      any-word matching, and the Gemini client rewrites the model's own citation styles into
      `[SOURCE:id]`. Verified live on NVDA.
- [ ] **Still no embeddings** (0 of 7,722 chunks): retrieval is keyword-only, so relevance is
      weaker than designed and Recall@5 can't be measured. Needs a Voyage key or a Gemini
      embedding client, then `scripts/embed_chunks.py`. `[code]`
- [ ] **No way to regenerate a report from the UI** when one already exists; the Research tab only
      offers "Generate" on a 404. `[code]`
- [ ] **Chat follow-up rule misfires**: any question of four words or fewer gets the previous
      message glued on, even when unrelated (`_is_followup` in `backend/app/chat/service.py`). `[code]`
- [ ] **Trend questions go to document search**: "How has revenue grown over the last three
      years?" is classed as an explanation, not answered from `financial_metrics`. `[code]`
- [ ] **`gemini-3.5-flash-lite` is a weak main model**: it left revenue, profitability and
      management sections empty where `gemini-3.8-flash` filled them, and varies its citation
      syntax between runs. `[code]`
- [ ] **Report prose shows raw numbers** ("215,938,000,000.00000000 USD"): the metric payload
      hands the model unformatted Decimals. `[code]`
- [ ] **Report took 171 s** against the 90 s target (NFR-003), with 4 s pacing between calls and
      one 60 s timeout. `llm_calls` still logs estimated tokens, not Gemini's reported usage. `[code]`
- [ ] **Publish measured numbers** (§36 #20): Recall@5, judge faithfulness, cost and latency per
      report/chat are `_pending_` in `README.md`. Needs a live Voyage + LLM eval run. `[code]`
  - [ ] Judge calibration ≥ 0.85 against a 50-question human-labelled sample (none committed). `[notes]`
  - [ ] Re-tune `rag_sufficiency_min_score`, entailment and confidence thresholds on real
        embeddings; decide reranker (ADR-0014) and entailment verifier (ADR-0015). `[notes]`
- [ ] **Hosted demo** (§36 #23): never deployed. `render.yaml`, Dockerfiles and `deploy.yml` exist;
      needs a Render account, repo secrets, branch protection. Public live prices are blocked by the
      Tiingo licence (ADR-0007), so the demo runs mock prices. `[notes]`
- [ ] **Load test never run**: every row of the NFR table in `docs/testing.md` says `_not yet run_`. `[code]`
- [ ] **E2E is manual-only** (`e2e.yml` is `workflow_dispatch`); Linux visual baselines are not
      committed; behavioural specs assume the dev DB, not the CI seed. `[code]` / `[notes]`
- [ ] **Price-derived metrics are not persisted** (market cap, EV, P/E, P/S, EV/EBITDA, FCF yield):
      `ratio_builder.py` has none. Leaves the valuation report section, dashboard header P/E and
      market cap, peer market-cap band and comparison valuation cells empty. `[code]`
- [ ] **Quarterly (Q1–Q3) and TTM metrics are not persisted** — only annual + derived Q4. The
      Financials Q/TTM toggles show empty states. `[code]`
- [ ] **Seed universe is 3 of 10**: fixtures cover NVDA, AAPL, JPM (AMD, INTC ingested live in dev).
      Missing MSFT, AMZN, TSLA, GOOGL (multi-class shares), META, V, MA (§4.1). `[code]`
- [ ] **Saved reports / research history / saved questions** (§26.2, §36 #24): reports carry a
      `user_id` but there is no list endpoint and no UI. `[code]`
- [ ] **Watchlist items**: no add/remove-item endpoint; each watched company is its own
      watchlist (ADR-0031 stand-in). Needs `POST/DELETE /watchlists/{id}/items` + a data migration. `[code]`
- [ ] Alerts: `POST /alerts` takes no `config` (price-move threshold, news category);
      `Notification` has no ticker. `[code]` / `[notes]`
- [ ] Email: no delivery provider for verify-email / password-reset; `email_verified_at` gates
      nothing; SMTP backend unproven. `[code]` / `[notes]`
- [ ] API has no response compression (prices ≈ 179 kB per company); mobile Lighthouse on the
      company page is 76–79 against a target of 90. `[code]` / `[notes]`

### Report-level features (§10.16)

- [ ] `GET /research/{id}/export` is 501 (Markdown export and print are client-side only). `[code]`
- [ ] `GET /research/{id}/diff` ("what changed since last report") is 501. `[code]`
- [ ] Shareable read-only links: not built. `[code]`
- [ ] Rejected-claims admin view: not built (data is logged in `claim_verifications`). `[notes]`
- [ ] `POST /feedback/report` is a 204 no-op (`backend/app/api/watchlist.py:153`). `[code]`

### Before any public deploy

- [ ] Unbounded free-text request fields — only chat `question` and compare `tickers` are capped.
      `password` (unauthenticated), `FeedbackRequest.reason`, `WatchlistCreate.name`,
      `ChatRequest.company`, `metrics`, search `q`. No request body size limit found. `[code]`
- [ ] DB gate in `get_db` (10 slots) has no wait timeout → queues in memory, never 503s. `[notes]`
- [ ] Product sign-off on AI budget placeholders ($5/user/month, $0.50 in demo, $25/day global). `[notes]`

## 2. Spec features not built (P2)

- [ ] **Insiders & ownership** (§10.15): no Form 4 / 13F ingestion; endpoints return `[]`; the
      `ownership` route redirects to overview. Appendix F #10 still undecided. `[code]`
- [ ] **DCF and scenario tools** (§37.6): nothing exists. `[code]`
- [ ] **Earnings-quality dashboard** (§37.7): accruals, Piotroski and Altman formulas exist but
      are not persisted; Beneish M is missing; DSO/DIO/DPO/CCC, ROIC, dilution, CAGR also
      unpersisted; no UI. `[code]`
- [ ] **Guidance vs actual** (§37.3): needs 8-K EX-99.1 exhibit ingestion or a licensed
      estimates source. Transcripts are deferred (ADR-0011). `[notes]`
- [ ] **Report analytics** (§10.3–10.7): revenue waterfall, seasonality, segment/geo mix
      (dimensional XBRL), margin bridge, valuation percentile bands. `[notes]`
- [ ] **RAG / AI**: semantic cache (RAG-050); cheap-model intent classifier and query rewriter;
      `get_filing_diff` and `get_insider_transactions` tools; conversation-aware rewrite;
      true incremental token streaming. `[code]` / `[notes]`
- [ ] **Citations**: numeric auto-repair (reject-only today); NLI / LLM-judge entailment. `[notes]`
- [ ] **Documents**: PDF parsing (DP-005); iXBRL cross-check not wired into the pipeline;
      anomaly identity/YoY checks not wired; no endpoint for full in-app filing text. `[code]` / `[notes]`
- [ ] **News**: tab shows 25 items with no paging; categorizer is rule-based; no sentiment
      (spec marks it optional). `[notes]`
- [ ] Filing diff is recomputed per request (not cached); `q4_derived:<metric>` source IDs are
      not company-scoped (`backend/app/finance/builder.py:230`). `[code]` / `[notes]`
- [ ] §37.8 P3 candidates (screener, sector dashboards, Excel export, …): untouched by design.

## 3. Never verified live

- [ ] Live Tiingo, Finnhub and Voyage paths (no API keys; parsing is unit-tested only). `[notes]`
- [ ] Prometheus / Grafana dashboards, OTLP exporter, MinIO object storage. `[notes]`
- [ ] A research report or comparison commentary from a real LLM, and the Research layout against one. `[notes]`
- [ ] Light theme screen by screen; real print preview; no toast system. `[notes]`
- [ ] `app/tasks/` wrappers are mostly 0% covered. `[notes]`

## 4. Housekeeping

- [ ] Definition of Done checkboxes in task files `01`–`25` were never ticked (every box is
      `[ ]`), although each phase was handed off as done. `UI_plan/` steps are ticked. `[code]`
