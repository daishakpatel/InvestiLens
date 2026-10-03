# ADR-0015: Deterministic entailment verifier for the MVP, NLI/LLM-judge deferred

- **Status:** Accepted
- **Date:** 2026-10-01
- **Spec refs:** §13.6 (CIT-005 L3), §14 (HAL-002), Appendix F item 7, ADR-0009, ADR-0014

## Problem

The citation verifier's entailment layer (CIT-005 L3) must decide whether a cited source actually
supports a claim (`supported | partially | unsupported`). The spec allows an NLI model or an
LLM-judge. A hosted NLI model (e.g. a `cross-encoder/nli` checkpoint) downloads weights at import
and breaks the offline unit suite and CI; an LLM-judge needs a key, cannot run offline, and — per
the Phase 2c/3 note — `claude-sonnet-5-5` rejects non-default sampling, so determinism rests on
recorded snapshots, not temperature 0. Phase 3a must be fully testable now against synthetic claims
and evidence, before any model key exists.

## Decision

Introduce an `Entailer` ABC (`app/citation/entailment.py`) with a deterministic **`LexicalEntailer`
as the MVP default**: content-word overlap between claim and cited source (stemmed, stopworded),
combined with the deterministic numeric-match result, mapped to `supported/partially/unsupported`
by configurable thresholds. The numeric-match and scope layers around it are already deterministic.
An `LLMEntailer` (using the existing `LLMClient`, ADR-0009) slots in behind the same ABC in Phase
3b/5b, and an NLI cross-encoder remains an option as a leaf library (allowed by ADR-0003). Which
verifier is used is config-driven; the lexical default ships now.

## Consequences

The entire citation pipeline — ID validation, numeric match, entailment, scope, coverage,
confidence, rendering — runs and is unit-/integration-tested offline today, deterministically
(NFR-010). The cost is that lexical entailment is weaker than a trained NLI model on paraphrase and
negation; that gap is measured, not assumed — Phase 5b's citation-accuracy eval (CIT-A2 ≥ 0.95,
HAL-A1) compares the lexical default against an LLM-judge/NLI verifier on the golden set, and we
promote whichever meets the bar. This resolves Appendix F item 7 for the MVP.
