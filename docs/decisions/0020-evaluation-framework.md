# ADR-0020: Evaluation framework, judge, and CI quality gate

- **Status:** Accepted
- **Date:** 2026-10-07
- **Spec refs:** §18 (evaluation framework), §5.1 (numeric targets), §38 (resume claims), EVAL-002, HAL-002, ADR-0009/0010 (model keys), ADR-0015/0014 (verifier/reranker)

## Problem

The resume/spec claims (Recall@K, citation accuracy, hallucination rate, abstention) must become
measured numbers that CI can defend, without re-implementing retrieval or citation verification
(those are Phase 2c/3a) and without live model keys in the default run. Some metrics are only
semantically meaningful with real embeddings/model: in mock mode retrieval uses deterministic hash
vectors and qualitative answers come from a FakeLLM, so Recall@K and LLM-judge faithfulness compute
but are not quality signals. Other metrics — numeric answer accuracy, abstention correctness,
citation accuracy (via the Phase 3a verifier's exposed labels), and hallucination rate — are fully
deterministic and meaningful offline.

## Decision

Build `app/eval/` as a measurement layer over the real pipeline: pure metric functions
(`metrics.py`: P@K/R@K/MRR/NDCG + Decimal numeric match), a pluggable `Judge` ABC (`LLMJudge` with a
versioned prompt `judge_v1` for live runs, `FakeJudge` offline), a `runner` that drives each golden
question through `chat.answer_question`/`run_retrieval` and persists to `eval_runs`/`eval_results`,
a `gate` (EVAL-002), an `ab` per-question diff, report-level eval, and feedback→golden triage. The
golden set is grown to 100+ via the reproducible `scripts/build_golden.py` (numeric questions
derived from the frozen `golden_metrics.json` so ground truth always matches the finance layer).
The **CI quality gate runs as a pytest integration test** (reusing the Postgres CI job, no bespoke
steps): it seeds a small corpus, runs the smoke subset, and asserts the gate catches a deliberate
citation-accuracy regression (allowed drift: Recall@5 ≤ 2 pts, citation accuracy ≤ 1 pt,
hallucination ≤ 0.5 pts vs baseline); the full set runs nightly via `scripts/run_eval.py`. The
committed `baseline.json` is the deterministic offline smoke baseline; a live full run replaces it.
Judge calibration (≥ 0.85 agreement vs human labels, §18.4) is implemented (`judge.calibrate`) and
run when a model key exists; offline we cannot calibrate a real judge, so that number is pending a
live run (same gate as ADR-0009).

## Consequences

CI now blocks quality regressions deterministically on the metrics that are meaningful offline
(citation accuracy, hallucination, abstention, numeric accuracy), and the harness is ready to emit
the live headline numbers (Recall@K, faithfulness, cost/latency) the moment Voyage + an LLM key are
configured. The cost is that the published README baseline is explicitly split into "measured
offline" and "pending live run" rather than a single blended number — honest, but it means the
Recall@K/faithfulness bullets stay provisional until the live run. The eval also surfaced and we
fixed one real gap (forward-looking "what will X be next year" was answered instead of abstained);
per task scope we do not otherwise hand-tune the pipeline here.
