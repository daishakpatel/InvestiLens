# ADR-0010: Embeddings — Voyage AI voyage-finance-2 (1024-dim)

- **Status:** Accepted
- **Date:** 2026-09-28
- **Spec refs:** §7, §16.4, §22, Appendix F item 3

## Problem

Retrieval quality over 10-K/10-Q language (MD&A, risk factors, footnotes, tables) drives
report quality. We need an embedding model that handles financial text well, with a dimension
pgvector can index efficiently.

## Decision

Use **Voyage AI `voyage-finance-2`** behind `EmbeddingClient`: finance-tuned, **1024
dimensions** (fixed), and a 32K-token context. Stored as `vector(1024)` in `document_chunks`
with an HNSW cosine index (1024 is well under pgvector's 2,000-dimension HNSW limit). Voyage's
`input_type` is set to `document` at index time and `query` at search time. Every chunk records
`embedding_model` so mixed-model data can be detected.

## Consequences

A domain-tuned model at a moderate dimension keeps index size and latency low. Voyage is
Anthropic's recommended embeddings partner, but it is still a second vendor and a second API
key. Changing models requires a full re-embed through a backfill job, which the recorded
`embedding_model` makes safe. The general-purpose `voyage-4` series is the comparison baseline
in the Phase 5b retrieval evals, and we switch if it measurably wins.
