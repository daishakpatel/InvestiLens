# ADR-0009: LLM provider — Anthropic Claude (two tiers)

- **Status:** Accepted
- **Date:** 2026-09-28
- **Spec refs:** §7, §16, §17, NFR-004, NFR-008, NFR-010, Appendix D

## Problem

We need a cheap, fast model for routing and classification, and a strong model for report
synthesis and chat. Both must reliably produce schema-valid structured output that cites only
the source IDs we supply.

## Decision

Use **Anthropic Claude** through the official `anthropic` Python SDK, behind `LLMClient`.
Prices are per million input/output tokens, as of 2026-09-25:

| Tier | Model ID | Price in/out | Used for |
|------|----------|--------------|----------|
| cheap | `claude-haiku-4-5` | $1 / $5 | query-intent classification, routing, 8-K item classification |
| strong | `claude-sonnet-5-5` | $2 / $10 | report section synthesis, chat answers |

Structured output uses the SDK's `messages.parse()` / `output_config.format` with our Pydantic
schemas. Anthropic's native document-citations feature is **not** used: it can't be combined
with structured output, and our citations must be backend-issued source IDs (CIT-001). Stable
system prompts use prompt caching. Every call checks `stop_reason` (including `refusal`) before
reading content, and is logged to `llm_calls` (NFR-015).

## Consequences

Model IDs are configuration, not code, so tiers can be re-pointed after evals.
`claude-opus-5-5` ($4 / $20) is the escalation option if evals (Phase 5b) show a quality gap on
synthesis. **Reproducibility note:** `claude-sonnet-5-5` doesn't accept non-default sampling
parameters, so "temperature 0" (NFR-010) can't be applied to the strong tier. Reproducibility
instead rests on snapshotting inputs, `data_version`, prompt version, and model ID, plus the
citation validator. Swapping providers means re-running evals, but no pipeline changes.
