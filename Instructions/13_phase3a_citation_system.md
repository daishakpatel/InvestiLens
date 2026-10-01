# Phase 3a — Citation System

**Prerequisites:** Phase 0 complete (schemas exist). Can start in parallel with Phase 1/2 since
it doesn't need real data — build and test it against Phase 0d's fixtures and mock evidence.
**Blocks:** `14_phase3b_research_report_generation.md` and `15_phase3c_chat_qa.md` — neither
can render a single claim without this.
**Full spec sections:** §13 (full citation system spec), §14 (hallucination prevention &
confidence), §15 (source quality hierarchy).

## Objective

Build the layer that makes or breaks this project's credibility: converting LLM output with
`[SOURCE:id]` markers into verified, numbered, clickable citations — and rejecting anything
that can't be proven.

## Scope

1. **Backend-issued source IDs (CIT-001):** the LLM never invents citation numbers. It emits
   `[SOURCE:<id>]` markers referencing IDs the backend handed it as part of the evidence
   context (from Phase 2c). The backend converts markers to sequential `[1]`, `[2]` in
   first-appearance order and drops any marker referencing an unknown ID.
2. **Source types and anchors (CIT-002):** implement the `SourceRecord` schema (already
   defined in Phase 0c) for all six types — `text_chunk`, `table_chunk`, `xbrl_fact`,
   `derived_metric`, `news_item`, `earnings_release`/transcript. Remember: HTML filings get
   `section_path` + `char_start/end` anchors, **not** page numbers; `page` stays null except
   for PDF sources.
3. **Lineage for derived numbers (CIT-003):** a `derived_metric` source must expose its
   formula, its input source IDs (chained back to `xbrl_fact` or other `derived_metric`
   records — this is exactly what Phase 1c's `MetricResult.inputs` was built to support), and
   the period. This powers the "How this was calculated" panel.
4. **Claim granularity (CIT-004):** citations attach to individual claims (sentence/clause),
   not whole paragraphs; store `claim_id`, `text`, `source_ids[]` per claim.
5. **Verification pipeline (CIT-005)** — implement all five layers, in order, for every
   generated claim:
   1. **ID validation** — every `source_id` must exist in the evidence set given for this
      request. Unknown → reject.
   2. **Numeric match** — extract numbers/percentages/dates/entities from the claim text; each
      must appear in the cited source (after unit normalization and a small rounding
      tolerance) or equal a value derivable from cited `derived_metric` inputs. Mismatch →
      reject, or auto-repair by substituting the backend's correct value if feasible.
   3. **Entailment check** — an NLI model or LLM-judge verifies the source actually supports
      the claim (`supported | partially | unsupported`). Unsupported → reject; partially →
      downgrade confidence or reject per a configurable policy.
   4. **Scope check** — reject claims that extrapolate beyond the source, especially causal
      language ("X caused Y") not actually present in the source; convert to correlation
      language or reject.
   5. **Coverage check** — any sentence with factual content but no citation → reject, or
      allow exactly one regeneration attempt.
6. **Rendering (CIT-006):** map accepted source IDs to sequential citation numbers; produce a
   reference list; every rejected claim is logged to `claim_verifications` with a reason code
   (`UNKNOWN_SOURCE`, `NUMERIC_MISMATCH`, `UNSUPPORTED`, `NO_CITATION`, `OVERREACH`).
7. **Confidence system (HAL-002):** compute an internal score from source count, tier,
   retrieval score, entailment result, and source agreement; expose only the label
   (`Strongly supported / Supported / Limited evidence`), never a raw model confidence number.
8. **Source quality hierarchy (§15):** implement the 5-tier lookup (SEC filings → earnings
   releases → IR materials/transcripts → licensed news → other) and apply it in both retrieval
   reranking (already partly done in Phase 2c) and confidence scoring here.
9. **`GET /sources/{source_id}` implementation** — this endpoint was contracted in Phase 0c but
   not implemented; build it here since it's this system's data. Returns the full source
   record, the text with the supporting span marked, and a deep link where available.

## Out of scope for this file

No report/chat generation logic — this file is purely the verification and rendering layer
that Phase 3b and 3c will call. Test it with synthetic claims and evidence, not real generated
reports (those come next).

## Definition of Done

- [ ] A claim citing an unknown source ID is rejected in every test case (CIT-A1)
- [ ] A claim with a number not present in (or derivable from) its cited source is rejected
- [ ] A claim with an unsupported causal statement is rejected or downgraded
- [ ] Accepted claims render with sequential citation numbers and a correct reference list
- [ ] Every rejection is logged in `claim_verifications` with an accurate reason code
- [ ] Confidence labels are calibrated such that, on a hand-built test set, "Strongly
      supported" claims are backed by strong evidence and "Limited evidence" claims are not
      (HAL-A1's spirit, even before the full eval harness exists in Phase 5b)
- [ ] `GET /sources/{source_id}` returns a working response for all six source types
