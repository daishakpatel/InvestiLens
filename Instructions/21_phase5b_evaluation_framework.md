# Phase 5b — Evaluation Framework

**Prerequisites:** `12_phase2c_rag_retrieval_pipeline.md`, `13_phase3a_citation_system.md`,
and `14_phase3b_research_report_generation.md`/`15_phase3c_chat_qa.md` all producing real
output. Uses the seed `golden_v0.jsonl` from Phase 0d as its starting point.
**Blocks:** this is what turns the resume claims in the main spec (§38) from guesses into
measured numbers — treat it as required, not optional polish.
**Full spec sections:** §18 (full evaluation framework), §5.1 (the specific numeric targets
this framework measures against).

## Objective

Build the harness that measures whether this system actually works — retrieval quality,
answer accuracy, citation accuracy, hallucination rate, and abstention correctness — and gate
CI on it so quality can't silently regress.

## Scope

1. **Grow the golden dataset** from Phase 0d's 10–15 seed questions to 100–200, following the
   format in spec §18.1 (`id, company, question, intent, expected_answer, expected_numeric,
   expected_sources, must_abstain, tags`). Cover: metric lookups, qualitative explanations,
   risk questions, management commentary, multi-hop questions, time-series questions,
   deliberate "should abstain" cases, out-of-scope-advice cases, prompt-injection cases, and at
   least one ambiguous-company case.
2. **Retrieval metrics:** Precision@K, Recall@K, MRR, NDCG against the golden set's
   `expected_sources`. MVP minimum is Recall@5 — get that solid first.
3. **Answer & citation metrics:**
   - **Answer accuracy** — deterministic exact-match for `expected_numeric` questions;
     LLM-as-judge (with a versioned judge prompt) for qualitative faithfulness.
   - **Citation accuracy** — does the cited source actually support the claim? Reuse Phase
     3a's verifier output directly rather than re-implementing this check.
   - **Hallucination rate** — unsupported claims that made it past verification (should be
     near zero if Phase 3a is working; this metric is your check on that).
   - **Abstention correctness** — does the system abstain on `must_abstain` questions and
     answer on the rest?
4. **Judge calibration:** where an LLM-judge is used, spot-check its agreement against human
   labels on a 50-question sample; target ≥ 85% agreement. Version the judge prompt like any
   other prompt.
5. **Eval runner:** a script/job that runs the full golden set against a fixed `data_version`,
   stores results in `eval_runs`/`eval_results` (from Phase 0b's schema), and produces a
   summary report.
6. **CI gating (EVAL-002):** run a small smoke subset on every PR; fail the PR if Recall@5
   drops more than 2 points, citation accuracy drops more than 1 point, or hallucination rate
   rises more than 0.5 points versus the `main` baseline. Run the full golden set nightly.
7. **A/B comparison harness:** ability to run the same golden set against two configurations
   (e.g. two prompt versions, two rerankers) and diff the results per-question — this is what
   lets you say "we tried X and it improved Y" credibly.
8. **Report-level eval:** section completeness, citation coverage (% of sentences with a
   citation), rejected-claim rate, cost per report, latency per report.
9. **Human feedback loop:** wire Phase 3c's chat feedback (thumbs down + reason) into a triage
   process that promotes flagged items into the golden set with a correct expected answer —
   this is what makes the eval set grow over time instead of staying frozen.
10. **Publish the baseline:** once a stable run exists, put the headline numbers (Recall@5,
    citation accuracy, hallucination rate, cost/latency) in the README — this is the number
    the resume bullets in the main spec's §38 should actually cite.

## Out of scope for this file

Don't rebuild retrieval or citation verification here — this file measures what Phase 2c/3a
already do. Don't hand-tune the RAG pipeline extensively based on eval results — that's
ongoing iteration after this framework exists, not part of building the framework itself.

## Definition of Done

- [ ] Golden dataset has 100+ questions covering every category listed above
- [ ] Retrieval, answer, citation, hallucination, and abstention metrics all compute correctly
      against a real run
- [ ] Judge-agreement spot check meets the ≥ 85% target, or the judge prompt is revised until
      it does
- [ ] CI smoke-gate blocks a PR that deliberately regresses citation accuracy (test this by
      temporarily breaking something and confirming the gate catches it)
- [ ] A/B harness produces a per-question diff between two configurations
- [ ] README shows real, measured baseline numbers — not placeholders
