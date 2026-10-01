# Phase 2b — Embeddings & Vector/Keyword Indexes

**Prerequisites:** `10_phase2a_document_parsing_chunking.md` done (real chunks with text and
anchors exist).
**Blocks:** `12_phase2c_rag_retrieval_pipeline.md` (searches what this file indexes).
**Full spec sections:** §22.4 (embedding rules EMB-001…004), §16.4 (storage requirements,
pgvector/HNSW/GIN setup — already created as indexes in Phase 0b, this file populates them).

## Objective

Generate embeddings for every chunk, populate the pgvector column, and make sure both
semantic (vector) and exact keyword (full-text) search actually work and are fast.

## Scope

1. **Implement the real `EmbeddingClient`** for the model/dimension chosen in ADR-0010
   (Phase 0a). Batch requests, retry with backoff, log cost per batch.
2. **Populate `document_chunks.embedding`** for every chunk from Phase 2a. Store
   `embedding_model` and `embedding_dim` on each row (EMB-001) — never assume a single global
   model version; this is what makes future re-embedding safe.
3. **Normalize vectors** before storage if your distance metric expects it (cosine similarity
   typically wants normalized vectors — confirm this matches how the HNSW index was configured
   in Phase 0b).
4. **Re-embedding / model migration path (EMB-003):** write the job that can re-embed all
   chunks under a new model without downtime — e.g. write to a new column/table, backfill, then
   swap, rather than embedding in place. You don't need to run a real migration now, but the
   mechanism must exist and be tested.
5. **Tune the HNSW index (EMB-004):** confirm `m`/`ef_construction` at index-build time and
   `ef_search` at query time are set sensibly for the corpus size; document the values and
   rationale in `docs/rag.md`.
6. **Keyword search:** confirm the `tsv` generated column from Phase 0b populates correctly
   from chunk text, and that exact financial terms ("restricted cash", "gross margin",
   "deferred revenue", "customer concentration") are retrievable via full-text search even when
   semantic search alone might miss them (write a specific test with one of these phrases).
7. **Cost and latency logging:** every embedding batch call logged (tokens, cost, latency) —
   reuse the `llm_calls`-style logging pattern even though this is an embedding call, not a
   chat completion, so cost tracking is consistent project-wide.
8. **Basic similarity smoke test:** embed a query like "NVIDIA supply chain risk" and confirm
   the top results are plausibly relevant chunks from the Risk Factors section — this is a
   sanity check, not the full retrieval pipeline (that's Phase 2c).

## Out of scope for this file

No query rewriting, no fusion of vector + keyword results, no reranking, no LLM orchestration —
all of that is Phase 2c. This file only makes sure chunks are embedded and both index types
work individually.

## Definition of Done

- [ ] Every chunk from Phase 2a has a non-null `embedding`, `embedding_model`, and
      `embedding_dim`
- [ ] A cosine-similarity query against the HNSW index returns results in the expected order
      for a hand-checked test query
- [ ] Full-text search correctly finds a chunk containing an exact phrase like "gross margin"
      even when phrased differently in the query
- [ ] The re-embedding/migration job runs end-to-end in a test (small fixture set, old model →
      new model) without data loss or downtime in the test scenario
- [ ] Embedding batch calls are logged with token count, cost, and latency
- [ ] `docs/rag.md` documents the index parameters and why they were chosen
