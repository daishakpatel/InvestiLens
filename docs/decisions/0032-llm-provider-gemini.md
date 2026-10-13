# ADR-0032: LLM provider — Google Gemini (two tiers), supersedes ADR-0009

- **Status:** Accepted
- **Date:** 2026-10-12
- **Spec refs:** §7, §16, §17, NFR-004, NFR-008, NFR-010, NFR-015, RAG-050, SEC-001, SEC-015

## Problem

ADR-0009 chose Anthropic Claude, but no live client was ever built, so every report and chat
answer has come from a fake model. The project owner wants a real model at no cost while the
project is a portfolio piece. The Gemini Developer API has a free tier that covers the models
needed; the Anthropic API has none.

## Decision

Use **Google Gemini** behind `LLMClient` (`app/providers/gemini.py`), calling the REST
`generateContent` endpoint through `HardenedHttpClient` like the other live providers, so no
vendor SDK is added. Prices are paid-tier list prices per million input/output tokens, as of
2026-10-12; the free tier costs nothing.

| Tier | Model ID | Paid price in/out | Used for |
|------|----------|-------------------|----------|
| cheap | `gemini-3.5-flash-lite` | $0.30 / $2.50 | filing-diff adjudication, classification |
| strong | `gemini-3.8-flash` | $0.75 / $3.75 until 2026-12-31, then $1.50 / $7.50 | report sections, chat answers, comparison commentary, eval judge |

`LLM_PROVIDER=gemini` selects it independently of `PROVIDER_MODE`, so a real model can run over
fixture prices, news and embeddings without the other providers' keys. Structured output uses
Gemini's JSON mode, not schema mode: schema mode rejects the open object schemas the report
sections pass, and every caller already validates the reply. Thinking is set to `low` and the
caller's token cap is raised by a fixed allowance, because Gemini counts thinking tokens against
the cap.

## Consequences

Real reports and chat answers at $0, and the live eval run becomes possible. Costs of the free
tier: Google may use the content sent (filing excerpts, user questions) to improve its products,
which a public demo must disclose or avoid by moving to the paid tier; the free tier allowed only 20
requests per day on `gemini-3.8-flash` when measured on 2026-10-12, and one report makes 10–14,
so free use covers about one report a day; calls are paced by `LLM_RATE_LIMIT_PER_SEC`. `llm_calls.cost_usd` is still estimated at list price so
per-user budgets (ADR-0022) keep limiting usage. Writing quality against Claude is unmeasured:
the golden-set eval (ADR-0020) decides whether to stay, and returning to Anthropic means one new
client class behind the same interface. The NFR-010 reproducibility note in ADR-0009 still
applies (snapshots, `data_version`, prompt version and model ID, not sampling parameters).
