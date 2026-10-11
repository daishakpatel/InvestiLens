# ADR-0027: Filing diff, management-language tracking & earnings reaction (Phase 6b)

- **Status:** Accepted
- **Date:** 2026-10-10
- **Spec refs:** §37.3, §37.4, §37.5, §10.10; CIT-001, RAG-016, RAG-040, NFR-009, FR-007, ADR-0006

## Problem

Phase 6b compares two filings and tracks management's wording over time. Five things had no prior
decision: (1) Phase 2a chunks are retrieval-sized, not risk-factor-sized, and carry no styling, so
"an individual risk factor" does not exist in the data and the task forbids re-chunking; (2) §37.4
asks for embedding similarity, but no chunk has an embedding and mock embeddings are hash vectors
with no meaning (no Voyage key, ADR-0010); (3) §37.4 asks for LLM adjudication of borderline
pairs, but the diff endpoint is public and ADR-0006 gives anonymous users no AI; (4) §37.3 wants
guidance/expectations vs actuals only where the data source is licensed for it; (5) what counts as
"management commentary" while transcripts are deferred (ADR-0011).

## Decision

(1) **Units are rebuilt at read time** (`app/filings/units.py`) by walking a filing's chunks
paragraph by paragraph and regrouping under headings; chunks are untouched. A risk-factor caption
is recognised from the **raw filing's bold/italic runs** (read from object storage), because a
one-sentence-paragraph heuristic alone reported a body sentence as a "new risk factor" on NVDA's
FY2026 10-K. The heuristic remains the fallback when the raw document is missing or unstyled, and
the response says which was used (`caption_detection`). (2) **Similarity is a seam**
(`diff_similarity`): word-bigram Jaccard by default (deterministic, offline), `EmbeddingClient`
cosine when set to `embedding`. Thresholds (`diff_match_threshold` 0.45, `diff_borderline_threshold`
0.20) are tuned for the lexical measure on four NVDA 10-K pairs and must be re-tuned for
embeddings. "Unchanged" means equal after digit masking, the same rule as Phase 2a's `dedup_hash`
(RAG-016). (3) **The LLM adjudicates only on the report path**, which already has a user and a
budget: it returns one boolean for a borderline pair, capped at `diff_max_llm_adjudications` and
logged to `llm_calls`. `GET /filings/{id}/diff` and the alert loop never call an LLM; there an
unadjudicated borderline pair is kept as `reworded` with `decided_by="threshold"`. Nothing is
persisted: a 10-K diff takes about 0.3 s. (4) **Guidance vs actual is not built.** No ADR licenses
an expectations/estimates source (ADR-0007 Tiingo and ADR-0008 Finnhub free tiers do not), and 8-K
press-release exhibits (EX-99.1), where a company's own guidance lives, are not ingested. Earnings
get a deterministic **price reaction** instead: adjusted close of the last session before the
Item 2.02 8-K's filing date to the first session after it. (5) **Management language** is counted
over MD&A text with a versioned phrase list (`topic_taxonomy_v1`) and hedging lexicon
(`hedging_lexicon_v1`), per 1,000 words, returning every counted sentence with its source ID.

## Consequences

Diffs are reproducible, cheap, and cited on both sides, and a report's `Risk.change_status` comes
from the same engine. Costs: the public endpoint and a report can disagree on a borderline pair
(one is adjudicated, one is not); caption detection depends on object storage being reachable;
the lexical thresholds are calibrated on one company; 10-Q diffs cover risk factors and Part II
only, and language tracking is 10-K only, because the Phase 2a section detector drops a 10-Q's
Part I (MD&A). Revisit when a Voyage key exists (re-tune and switch `diff_similarity`), when an
estimates licence or EX-99.1 ingestion lands (guidance tracker), or when the chunker stores
emphasis (drop the raw-document read).
