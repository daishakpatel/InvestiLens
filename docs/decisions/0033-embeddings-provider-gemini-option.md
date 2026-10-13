# ADR-0033: Gemini as a second embedding provider, alongside Voyage (ADR-0010)

- **Status:** Accepted
- **Date:** 2026-10-12
- **Spec refs:** §7, §16.4, §22.4, RAG-010, EMB-001, EMB-002, EMB-003, SEC-001, SEC-015

## Problem

ADR-0010 chose Voyage `voyage-finance-2`, but no Voyage key exists and no chunk in the dev
database was ever embedded. Retrieval therefore ran on keyword search alone, and full-sentence
questions were declined. The project now has a Gemini key (ADR-0032), and the Gemini Developer
API embeds text on its free tier.

## Decision

Add `GeminiEmbeddingClient` (`app/providers/gemini.py`) behind `EmbeddingClient`, using
`gemini-embedding-2` through the REST `batchEmbedContents` endpoint and `HardenedHttpClient`.
`outputDimensionality` is set to the project's 1024, so vectors fit the existing `vector(1024)`
column and HNSW index with no migration. `EMBEDDING_PROVIDER=gemini` selects it independently of
`PROVIDER_MODE`; Voyage stays available and remains the live default. Vector search now matches
only chunks embedded by the active model, so switching provider yields no neighbours (keyword
search still answers) until `scripts/embed_chunks.py` re-embeds, instead of ranking at random.
That script commits per batch so a quota error costs one batch.

## Consequences

Semantic retrieval works at $0 and Recall@5 becomes measurable. `gemini-embedding-2` is a general
model, not finance-tuned like `voyage-finance-2`; the golden-set eval (ADR-0020) decides whether
the difference matters. Vectors from the two providers are not interchangeable: changing provider
means re-embedding every chunk (the in-place path, since the dimension is unchanged; ADR-0013).
On the free tier Google may use the text sent, which is public filing text plus user questions
(same note as ADR-0032). `embedding_cost_per_1m_tokens` still holds Voyage's price; set it to
0.20 when using Gemini's paid tier.
