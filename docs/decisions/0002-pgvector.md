# ADR-0002: pgvector, not a dedicated vector database

- **Status:** Accepted
- **Date:** 2026-09-28
- **Spec refs:** §20 (Database), NFR-002, NFR-007

## Problem

Retrieval needs vector similarity search over filing and news chunks, joined with relational
filters (company, filing type, fiscal period, section). A separate vector DB (Pinecone,
Weaviate, Qdrant) means a second datastore to sync, secure, back up, and pay for.

## Decision

Use the `pgvector` extension inside PostgreSQL 16 for MVP, with HNSW indexes (cosine distance)
on `document_chunks`. Keyword search uses Postgres full-text search in the same database, so
hybrid retrieval is one system.

## Consequences

Chunks, metadata, and embeddings stay transactionally consistent, relational filters are plain
SQL, and there's one datastore to operate. Target scale (500 companies × 5 years, NFR-007) is
well within pgvector's range. We revisit if retrieval p95 exceeds 400 ms for top-20 (NFR-002) at
real scale. The retrieval code sits behind a repository, so a migration would stay local.
