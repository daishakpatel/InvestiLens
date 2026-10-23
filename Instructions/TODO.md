# Assay Desk — Remaining Work

Audited 2026-10-12 against `docs/AssayDesk_Spec_v2.md`; last updated 2026-10-15. All 25 task
files and the 5 `UI_plan/` steps have been worked through; this is what is still open.

Tags: `[code]` = checked in the code, database or CI on the date shown in the item or, if none,
the audit date. `[notes]` = carried from earlier session hand-offs, not re-checked.

## State on 2026-10-14

- CI on `develop` is green at `0b3cc01`.
- **Not yet committed:** stored valuation metrics (ADR-0036), readable figures in AI reports
  (prompt `report_v2`), the frontend's handling of multiples, their tests and docs. All 516
  backend tests and 77 frontend tests pass with them; finance and citation coverage is 100%.
- Gemini billing is on ($10 credit added 2026-10-14). Local `.env`: `LLM_PROVIDER=gemini`,
  `LLM_MODEL_STRONG=gemini-3.5-flash-lite`, `EMBEDDING_PROVIDER=gemini`, `PRICE_PROVIDER=tiingo`,
  `REFRESH_PRICES_ON_STARTUP=true`. News is still sample data.
- Dev database: five companies (NVDA, AAPL, JPM, AMD, INTC) with real SEC financials, real prices
  and stored valuations. Filing text is parsed and embedded for all five (19,808 passages).
  Fresh research reports for JPM, AAPL and INTC (2026-10-15, `gemini-3.8-flash`); NVDA's and AMD's
  are from earlier the same day.

## 0. Broken right now

- [ ] `GET /companies/{ticker}/research/latest` returns 500 when the stored report fails validation
      (`ResearchReport.model_validate` is unguarded in `backend/app/api/companies.py`). `[code]`
- [ ] Filings list pages by `id desc`, not filing date (`backend/app/repositories/filings.py`);
      the Filings tab works around it by fetching 200 and sorting. `[code]`
- [ ] **Intel's filings have no sections**: its 10-K has no "Item N" headings (annual-report layout,
      headings likely images), so it is kept as one flagged "Filing text" section. Chat and reports
      work; section-aware features (management language, filing diff by section) do not. `[code]`
- [ ] **JPM's 10-K is mis-sectioned**: 1,523 of its 2,463 passages are labelled "Item 15. Exhibits",
      because JPM binds its annual report (MD&A, financials) after that heading. Answers still work,
      but section-aware features (management commentary, language tracking) miss it. `[code]`
- [ ] **Older submission pages are re-read on every ingest**: since Phase 7c `list_filings`
      pages through `filings.files[]` back to the longest backfill window (JPM: dozens of pages
      per run). The pages are immutable history; caching them would save SEC requests. `[code]`
- [ ] **JPM's 10-Q has no Part I item headings** (cross-reference layout): its financial
      statements and MD&A are kept as one "Part I" section (`10q_part1_unitemized`) and flagged
      low-confidence, not split into Item 1 / Item 2. `[code]`
- [ ] **Table figures in millions fail the answer checker**: a claim quoting "$19,827 million" from
      a table whose cells read "19,827" (in millions) is rejected as a mismatch. `[code]`
- [ ] **Browser tests assume AMD has no prices**: `e2e/tests/company.spec.ts`, `tools.spec.ts`
      and `screenshots.spec.ts` use AMD for the "no price history" case, which is no longer true
      in the dev DB. The visual suite replays recorded responses and is unaffected. `[code]`

## 1. Decisions waiting on the project owner

- [ ] **Main report/chat model.** With billing on, the free-tier cap on `gemini-3.8-flash` (20
      requests a day) no longer binds. It wrote fuller reports than `gemini-3.5-flash-lite` (which
      left revenue, profitability and management sections empty); measured about $0.05 per report
      on either. Switching is one `.env` line: `LLM_MODEL_STRONG=gemini-3.8-flash`. `[code]`
- [ ] **Commit** the uncommitted work listed above.
- [ ] Product sign-off on AI budget placeholders ($5/user/month, $0.50 in demo, $25/day global). `[notes]`
- [ ] Form 4 / 13F in scope or not (spec Appendix F #10). `[notes]`

## 2. MVP Definition of Done (spec §36) — not yet met

### AI answers and reports

- [ ] **`gemini-3.5-flash-lite` is a weak main model**: it left revenue, profitability and
      management sections empty where `gemini-3.8-flash` filled them, writes Markdown although told
      not to (stripped before checking), and varies its citation syntax (the client normalises four
      styles). `[code]`
- [ ] **No way to regenerate a report from the UI** when one already exists; the Research tab only
      offers "Generate" on a 404. Generating one costs about $0.05–0.10 on the paid tier. `[code]`
- [ ] **News summary is empty in every report**: news is still sample data. `[code]`
- [ ] **Report sections search with fixed keywords and no preference for recent filings**
      (`_SECTION_QUERY` in `backend/app/research/report.py`): NVDA's bull case picked up crypto
      "mining demand" from older 10-Ks, and AMD's management section quoted forward-looking-
      statement boilerplate. `[code]`
- [ ] **Price questions go to document search**: "what was the stock high on Sep 29" or "stock price
      today" are not answered from `price_history` (prices have no citable source type yet). One
      such question sent 23k tokens of context, well over the 6,000-token budget. Plain "margins"
      is not in the metric lexicon, so "how did margins trend?" goes to the filings. `[code]`
- [ ] **`llm_calls` logs estimated tokens**, not Gemini's reported usage (that goes to the
      application log only), so cost tracking and budgets run on estimates. `[code]`
- [ ] **Report speed**: about 70 s on `gemini-3.5-flash-lite` (18 calls), 171 s on `gemini-3.8-flash`
      with free-tier pacing, against a 90 s target (NFR-003). `LLM_RATE_LIMIT_PER_SEC` (0.25) can be
      raised now that billing is on. `[code]`
- [ ] Comparison commentary and filing-diff adjudication have never run on a real model. `[notes]`

### Measured numbers (§36 #20)

- [ ] **Publish** Recall@5, judge faithfulness, cost and latency per report/chat; they are
      `_pending_` in `README.md`. Now unblocked (corpus embedded, billing on): needs a live eval
      run of about 106 questions, roughly $1–2. `[code]`
  - [ ] Judge calibration ≥ 0.85 against a 50-question human-labelled sample (none committed). `[notes]`
  - [ ] Re-tune `rag_sufficiency_min_score`, entailment and confidence thresholds on real
        embeddings; decide reranker (ADR-0014) and entailment verifier (ADR-0015). `[notes]`
- [ ] **Load test never run**: every row of the NFR table in `docs/testing.md` says `_not yet run_`. `[code]`

### Data

- [ ] **Valuation uses fiscal-year figures, not TTM** (ADR-0036): P/E late in a fiscal year uses
      earnings up to ten months old. TTM EPS, revenue, FCF and EBITDA are stored since Phase 7b
      (ADR-0040, `period_type` TTM); switching `valuation_builder` to them is Phase 7h. `[code]`
- [ ] **AMD pretax income and AMD/Intel D&A are not mapped quarterly**: their tags are missing
      from the concept map, so `metric_gaps` lists them and their TTM effective tax rate, ROIC
      and EBITDA are absent (checked 2026-10-21 on the dev DB). `[code]`
- [ ] **AMD and Intel have no total liabilities tag** (Phase 7d): their Altman Z is
      `insufficient_data` (missing `total_liabilities`), and so are their balance-sheet accruals.
      Deriving it as assets − equity was rejected because of temporary equity (ADR-0042). Altman's
      original Z also needs a fiscal-year-end price, so years before the stored price history
      are insufficient. `[code]`
- [ ] **Peer percentiles compare latest fiscal years, not calendar years** (Phase 7d): NVIDIA's
      January year sits beside December years; the comparison engine's calendarization is not
      used here. `[code]`
- [ ] **Quarterly ratios are not stored** (quarterly gross/operating margin, ROE): only TTM
      ratios are (Phase 7b scope). The Financials Quarterly view therefore hides the Margins
      charts. `[code]`
- [ ] **TTM EPS right after a split**: the identity takes each term's latest restatement, but a
      split after the last 10-K and before any filing restates the prior year still mixes share
      bases; the `share_count_changed` flag marks such windows (ADR-0040). `[code]`
- [ ] **Five-year average multiples** (spec §10.7 "5Y Average P/E") are not computed; the
      per-year history is stored, so this is a deterministic average in the report payload. `[code]`
- [ ] **EV/EBITDA is N/A for AMD and Intel**: their depreciation & amortization is not mapped in
      the concept map, so EBITDA is missing. `[code]`
- [ ] A latest-close valuation is replaced on every price run, so a report that cited yesterday's
      dated ID (`derived:NVDA:pe_ratio:<date>`) no longer resolves it. `[code]`
- [ ] **Seed universe is 5 of 10 in dev, 3 in fixtures** (fixtures: NVDA, AAPL, JPM). Missing
      MSFT, AMZN, TSLA, GOOGL (multi-class shares), META, V, MA (§4.1). `[code]`
- [ ] **News is sample data** (placeholder headlines); live news needs a Finnhub key, and a
      `NEWS_PROVIDER` switch like the ones for the LLM, embeddings and prices. `[code]`
- [ ] **New SEC filings arrive only when ingestion is run by hand** locally. Prices catch up at
      API start; filings have no equivalent. `[code]`
- [ ] Prices refresh only at API start, and the check is "older than 12 hours", not "has the
      market closed since". Fine for local use; a hosted deploy uses the `price-eod` schedule. `[code]`

### Accounts and user features (§26.2, §36 #24)

- [ ] **Saved reports / research history / saved questions**: reports carry a `user_id` but
      there is no list endpoint and no UI. `[code]`
- [ ] **Watchlist items**: no add/remove-item endpoint; each watched company is its own
      watchlist (ADR-0031 stand-in). Needs `POST/DELETE /watchlists/{id}/items` + a data migration. `[code]`
- [x] Alerts: `POST /alerts` takes no `config` (price-move threshold, news category);
      `Notification` has no ticker. Done in Phase 7a (ADR-0039): typed `params`, `ticker` on
      notifications, `/alerts` settings page. `[code]` / `[notes]`
- [ ] Email: no delivery provider for verify-email / password-reset; `email_verified_at` gates
      nothing; SMTP backend unproven. `[code]` / `[notes]`
- [ ] Alerts (Phase 7a leftovers): `filing:<id>` / `price:…` evidence ids don't resolve via
      `GET /sources/{id}` (the UI maps them to routes); email is sent before the dispatch job
      commits, so a crash in that window can resend one (ADR-0039); `price_move` checks only the
      newest bar per company; the generic form shows the price threshold as a raw fraction. `[code]`

### Report-level features (§10.16)

- [ ] `GET /research/{id}/export` is 501 (Markdown export and print are client-side only). `[code]`
- [ ] `GET /research/{id}/diff` ("what changed since last report") is 501. `[code]`
- [ ] Shareable read-only links: not built. `[code]`
- [ ] Rejected-claims admin view: not built (data is logged in `claim_verifications`). `[notes]`
- [ ] `POST /feedback/report` is a 204 no-op (`backend/app/api/watchlist.py`). `[code]`

### Deployment and tests

- [ ] **Hosted demo** (§36 #23): never deployed. `render.yaml`, Dockerfiles and `deploy.yml` exist;
      needs a Render account, repo secrets, branch protection. Tiingo's free plan is for personal
      use, so a public demo must show sample prices or use a paid plan (ADR-0007, ADR-0035). The
      Gemini key is on the paid tier now, so content is not used to improve Google's products. `[notes]`
- [ ] **E2E is manual-only** (`e2e.yml` is `workflow_dispatch`); Linux visual baselines are not
      committed; behavioural specs assume the dev DB, not the CI seed. `[code]` / `[notes]`
- [ ] API has no response compression (prices ≈ 179 kB per company); mobile Lighthouse on the
      company page is 76–79 against a target of 90. `[code]` / `[notes]`

### Before any public deploy

- [ ] Unbounded free-text request fields — only chat `question` and compare `tickers` are capped.
      `password` (unauthenticated), `FeedbackRequest.reason`, `WatchlistCreate.name`,
      `ChatRequest.company`, `metrics`, search `q`. No request body size limit found. `[code]`
- [ ] DB gate in `get_db` (10 slots) has no wait timeout → queues in memory, never 503s. `[notes]`
- [ ] `HardenedHttpClient` retries every 4xx, not only 429/5xx, so a bad API key is retried
      three times before failing. `[code]`

## 3. Spec features not built (P2)

- [ ] **Insiders & ownership** (§10.15): no Form 4 / 13F ingestion; endpoints return `[]`; the
      `ownership` route redirects to overview. `[code]`
- [ ] **DCF and scenario tools** (§37.6): nothing exists. `[code]`
- [ ] **ROIC (annual) and revenue CAGR are still unpersisted** (§37.7 leftovers): Phase 7d
      stores the earnings-quality measures (below, "Done") and 7b stores TTM ROIC, but no annual
      ROIC or multi-year CAGR row exists. `[code]`
- [ ] **Guidance vs actual** (§37.3): EX-99.1 press releases are ingested since Phase 7c
      (`earnings_release` documents); extracting the guidance numbers is Phase 7i. Transcripts
      are deferred (ADR-0011). `[code]`
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
- [ ] Filing diff is recomputed per request, not cached. `[notes]`
- [ ] §37.8 P3 candidates (screener, sector dashboards, Excel export, …): untouched by design.

## 4. Never verified live

- [ ] Finnhub (news) and Voyage (embeddings) paths: no API keys; parsing is unit-tested only. `[notes]`
- [ ] Prometheus / Grafana dashboards, OTLP exporter, MinIO object storage. `[notes]`
- [ ] The Celery Beat schedule and the full daily pipeline. `[notes]`
- [ ] Light theme screen by screen; real print preview; no toast system. `[notes]`
- [ ] `app/tasks/` wrappers are mostly 0% covered. `[notes]`

## 5. Housekeeping

- [ ] Definition of Done checkboxes in task files `01`–`25` were never ticked (every box is
      `[ ]`), although each phase was handed off as done. `UI_plan/` steps are ticked. `[code]`

## Done since the audit

- 2026-10-12 — **CI green**: an "offline" contract test needed a seeded database; the guard test
  for ADR-0029 checked no routes and hid an `async` `/metrics` handler; a Dependabot major bump
  (TypeScript 7) broke `npm ci`; the pinned Trivy release had been deleted. Dependabot no longer
  groups major versions.
- 2026-10-12 — **Live LLM**: Gemini behind `LLMClient` (ADR-0032), with `LLM_PROVIDER=gemini`.
  The root `.env` is now actually loaded by the backend, and tests ignore `.env` entirely.
- 2026-10-12 — **Chat answers**: keyword search falls back to any-word matching; the Gemini
  client rewrites the model's citation styles into `[SOURCE:id]`.
- 2026-10-12 — **Real embeddings**: Gemini `gemini-embedding-2` behind `EmbeddingClient`
  (ADR-0033). Vector search is limited to the active model; retrieval falls back to keyword
  search if the provider fails; `scripts/embed_chunks.py` is resumable.
- 2026-10-12 — **Readable numbers in chat** and the citation panel
  (`backend/app/finance/display.py`): "$215.94 billion", "71.07%".
- 2026-10-13 — **Net income / operating income answered with revenue**: every stored metric now
  has its own `source_id` (ADR-0034); dev metrics rebuilt (3,209 rows, 3,209 distinct IDs). The
  same change fixed a 500 from `GET /sources` for derived fourth-quarter figures.
- 2026-10-13 — **Real prices**: `PRICE_PROVIDER=tiingo` (ADR-0035), all five companies loaded
  2021-10-14 to 2026-10-13, sample data removed, and prices caught up at API start with
  `REFRESH_PRICES_ON_STARTUP=true`.
- 2026-10-13 — A real research report exists for NVDA in the dev DB (`gemini-3.5-flash-lite`).
- 2026-10-14 — **Embeddings complete**: all 7,722 parsed chunks embedded with Gemini on the paid
  tier (about 1.7 million tokens in total, roughly $0.35).
- 2026-10-14 — **Market cap, EV and multiples stored** (ADR-0036): per fiscal year and at the
  latest close, rebuilt with every price run, split-adjusted, bank EV multiples N/A. They fill
  the header, the Financials valuation panel, comparisons, peer market-cap bands and the report's
  valuation section.
- 2026-10-14 — **Readable figures in AI reports**: the report payload and evidence carry figures
  as "$215.94 billion" / "71.07%" / "46.63x" (prompt `report_v2`); a fresh NVDA report had no raw
  numbers in its 26 figure-bearing claims.
- 2026-10-14 — **Chat answers on AMD** (user report): Markdown (`*`, `**`, `###`) is removed before
  the answer is checked and the model is told not to write it; "risks"/"margins" now count as
  factual terms, so a cited answer is no longer declined because only its uncited sentence looked
  factual; a short question is no longer glued to the previous one unless it opens with a
  follow-up word or leans on a pronoun ("what does management attribute it to?"); semicolon-
  separated citations are split.
- 2026-10-15 — **JPM questions declined** (user report): JPM's and Apple's filings had only come
  from the sample set. Loaded five years from EDGAR, fixed the loader skipping a known filing whose
  stored document was missing (ING-001), parsed and embedded them (5,342 passages, about $0.16).
  `scripts/parse_filings.py` now takes tickers so other companies keep their embeddings.
- 2026-10-15 — **Trend questions answered from stored figures**: "How has revenue grown over the
  last three years?" (a "how", not a "why", naming a stored metric over several years) is answered
  from `financial_metrics` with year-on-year growth, for every company.
- 2026-10-15 — **Retrieval cap no longer starves single-filing companies**: the 3-per-filing cap
  only reorders; it fills from the same filing when no other filing can.
- 2026-10-15 — **Research reports for JPM, Apple and Intel** (user report): JPM's and Apple's were
  fake-model placeholders from 2026-10-11 and Intel had none; all three regenerated. The report
  payload now covers the last five fiscal years, says "not applicable for this sector" once
  instead of per year, leaves out metrics with no value, and adds ROE/ROA to profitability, so a
  bank's profitability section discusses net margin and returns. A 10-K with no "Item" headings
  (Intel) is now kept as one flagged section instead of being dropped (6,744 passages).
- 2026-10-21 — **Quarterly and TTM metrics persisted** (Phase 7b, ADR-0040): the last 12 fiscal
  quarters of every flow metric and balance, cash flows de-cumulated from YTD facts (the derived
  Q4 operating cash flow had never been produced), every complete TTM window with TTM margins
  and ROIC, and a `metric_gaps` table behind `GET /companies/{ticker}/metrics/coverage`.
  `/financials` takes `limit` and returns each point's source ID and formula; the Overview has
  an Annual / Quarterly toggle (quarterly bars, TTM line). Dev metrics rebuilt for all five
  companies. Caught on the way: TTM EPS mixed pre- and post-split figures (NVIDIA read -2.28),
  and `get_latest_metrics` would have let a quarter of the year in progress displace the annual
  figure in portfolio and research.
- 2026-10-22 — **SEC exhibits, extra forms and the 8-K item fix** (Phase 7c, ADR-0041): 8-K items
  are full dotted codes (5.02 and 5.07 were both "5"); 10-Q Part I (financial statements, notes,
  MD&A) is chunked again (Part II's item numbers had overwritten it, so it was never chunked);
  EX-99.1/99.2 of earnings 8-Ks are stored as tier-2 `earnings_release` documents; DEF 14A,
  DEFA14A, NT 10-K/NT 10-Q (`late_filing_notice`) and 8-K/A are ingested with per-form backfill
  windows; older submission pages are read, so JPM now has five years of 10-Ks and 10-Qs; the
  parse step skips current documents and keeps embeddings of unchanged text; `make reparse-8k`.
- 2026-10-22 — **Earnings-quality dashboard** (Phase 7d, ADR-0042): the Beneish M-score (8
  variables, −1.78 threshold, checked against a second source), the Altman Z variant chosen by SIC
  (original or Z″, stored with the result), Piotroski with all nine criteria, accruals
  (cash-flow and balance-sheet), DSO/DIO/DPO/CCC, FCF conversion and split-safe dilution. These
  are persisted per fiscal year with resolvable inputs, plus TTM FCF conversion and accruals.
  `GET /companies/{ticker}/earnings-quality` serves them with peer percentiles (hidden below
  three peers). The new Earnings quality tab has five cards, the caveat strip, a cash-vs-earnings
  chart, a five-year table and an inputs disclosure that opens the citation drawer. The verifier
  rejects fraud or manipulation wording on a cited score (`report_v3`). Caught on the way:
  NVIDIA's FY2026 marketable securities moved to a new tag, and the missing value would have
  been read as zero; NVIDIA's FY2022 dilution read +304% because the 2021 split predates the
  price history (now taken from the 10-K's restated comparative); derived lineage stored no input
  values.
