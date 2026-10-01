# RAG — Embeddings & Indexes (Phase 2b)

How `document_chunks` get embedded and how the two retrieval indexes are configured. Fusion,
reranking, query rewriting, and orchestration are Phase 2c and are **not** covered here. Sources:
spec §16.4, §22.4 (EMB-001…004), ADR-0010 (model), ADR-0013 (migration + tuning).

## Embedding model (ADR-0010)

| Property | Value |
|----------|-------|
| Provider / model | Voyage AI `voyage-finance-2` |
| Dimension | 1024 (fixed) — `vector(1024)` column |
| `input_type` | `document` at index time, `query` at search time |
| Vectors | L2-normalized (cosine == the index metric) |
| Batch size | 128 inputs/request (Voyage cap) |

Each chunk stores `embedding`, `embedding_model`, and `embedding_dim` (EMB-001) so a corpus can
hold mixed-model rows and re-embedding stays safe. `PROVIDER_MODE=mock` uses deterministic,
offline hash vectors of the same dimension; `live` uses Voyage (`VOYAGE_API_KEY` required, raises
if missing).

## Generation pipeline (EMB-002)

`app/embeddings/pipeline.py::embed_pending` reads chunks missing a vector for the active model,
embeds them in batches, and writes vectors back with their model + dim. **Every batch is logged to
`llm_calls`** (`purpose = "embedding"`) with token count, cost, and latency — the same cost table
used for chat completions, so embedding spend is tracked project-wide. Token counts come from
Voyage's reported usage when available, else the project `~4 chars/token` estimator (cost column
only; no financial output depends on it). Run: `cd backend && uv run python ../scripts/embed_chunks.py`.

## Re-embedding / model migration (EMB-003, ADR-0013)

Zero-downtime swap, in `app/embeddings/reembed.py`:

1. **Stage** — `stage_all` embeds every chunk under the new model into the `embedding_new` staging
   column. The live `embedding` column keeps serving reads the whole time. Resumable: only
   un-staged rows are embedded.
2. **Swap** — `swap` runs one atomic `UPDATE` promoting staged vectors to `embedding` and stamping
   the new `embedding_model` / `embedding_dim`, then clears staging. Only rows that were staged are
   touched, so a crash mid-backfill never loses data.

`migrate_model` runs both. A model with a **different dimension** requires a separate column-retype
migration (see ADR-0013); the swap mechanism assumes a dimension-preserving change (both Voyage
models are 1024-dim).

## Indexes

### Vector — HNSW cosine (EMB-004)

Index: `ix_document_chunks_embedding_hnsw` on `embedding`, `vector_cosine_ops`.

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `m` | 16 | pgvector default; graph degree is ample for a tens-of-thousands-chunk MVP corpus and keeps build fast. |
| `ef_construction` | 64 | pgvector default; good recall/build-time balance at this scale. |
| `ef_search` | 100 (per query) | Raised from the default 40 for better recall at negligible latency on this corpus; set `SET LOCAL hnsw.ef_search` per query so it can vary by query class. |

Values are revisited in the Phase 5b retrieval evals against measured recall/latency on the full
corpus. `ef_search` is `app.config.hnsw_ef_search` (default 100).

### Keyword — full-text GIN

Index: `ix_document_chunks_tsv` (GIN) on the generated `tsv` column
(`to_tsvector('english', text)`). Queries use `websearch_to_tsquery('english', …)` so English
stemming lets exact financial terms match differently-phrased queries ("gross margin" ↔ "gross
margins", "restricted cash", "deferred revenue", "customer concentration"). This is the safety net
for exact-term recall that pure semantic search can miss.

### Usage

`app/rag/search.py` exposes `vector_search`, `vector_search_by_vector`, and `keyword_search` —
each over **one** index, company-scoped (RAG-013). Combining them (RRF fusion, reranking) is
Phase 2c.
