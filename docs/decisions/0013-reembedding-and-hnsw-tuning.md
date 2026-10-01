# ADR-0013: Re-embedding via column swap; HNSW tuning for MVP corpus

- **Status:** Accepted
- **Date:** 2026-10-01
- **Spec refs:** §16.4, §22.4 (EMB-001…004), ADR-0002, ADR-0010

## Problem

Phase 2b must populate `document_chunks.embedding` and make both vector and keyword search fast,
while staying safe to re-embed when the model changes (EMB-003) — ADR-0010 names `voyage-4` as a
future comparison baseline, so a model swap is expected, not hypothetical. Two choices need
settling: how to migrate models without blanking the live index, and what HNSW parameters suit a
corpus that is only tens of thousands of chunks for the MVP seed set.

## Decision

**Migration = staging column + atomic swap, in one table.** We add `embedding_dim` (per-row,
beside `embedding_model`, EMB-001) and a nullable `embedding_new vector(1024)` staging column. A
model change backfills `embedding_new` while `embedding` keeps serving reads; a single
`UPDATE … SET embedding = embedding_new, embedding_model = :new, embedding_dim = :dim,
embedding_new = NULL WHERE embedding_new IS NOT NULL` promotes it atomically. We chose this over a
separate `document_chunk_embeddings` table because §16.4 reads `document_chunks.embedding` directly
and one table keeps retrieval queries simple; a dimension-preserving swap (both Voyage models are
1024-dim) is the common case. A model with a *different* dimension needs a one-off column retype
(the "new table" variant) — out of scope until it happens. **HNSW:** keep `m = 16`,
`ef_construction = 64` (pgvector defaults, ample for this corpus size and cheap to rebuild) and set
`hnsw.ef_search = 100` per query (up from the default 40) for better recall at negligible latency.

## Consequences

Re-embedding is zero-downtime, resumable (only un-staged rows are embedded), and crash-safe (the
swap only touches staged rows), all without a second vector table or read-path changes. The cost is
one extra nullable vector column (NULL except during a migration) and the standing rule that a
dimension change is a separate migration. HNSW values are documented in `docs/rag.md` and are
revisited in the Phase 5b retrieval evals, where `ef_search` and `m` are tuned against measured
recall/latency on the full corpus.
