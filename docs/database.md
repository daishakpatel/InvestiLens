# Database

PostgreSQL 16 + [pgvector](https://github.com/pgvector/pgvector) ([ADR-0002](decisions/0002-pgvector.md)).
Models live in `backend/app/models/`; migrations in `infrastructure/migrations/` (Alembic).
This doc is the map — the models are the source of truth, and any schema change updates this
file in the same PR (DB-001).

## Conventions (spec §23.4, docs/conventions.md)

- **Money** is `NUMERIC(24,4)` (`Money` type alias). **Ratios / derived values** are
  `NUMERIC(28,8)` (`Quantity`), which also holds share counts that exceed integer ranges.
  **No monetary column is ever float** (DB-003, checked by a migration test).
- **Timestamps** are `TIMESTAMPTZ`, stored in UTC. **Fiscal-period fields** are separate
  columns, never derived from calendar dates.
- **Primary keys** are `BigInteger` identity (headroom for NFR-007's 10× growth).
- **Constraint/index names** follow a fixed naming convention (see `app/models/base.py`) so
  migrations stay deterministic and reviewable.

## Tables by domain (33 tables)

```text
Reference        companies ──< company_identifiers
                 companies ──< fiscal_calendars

Documents        companies ──< documents ──< filings (filings.amends_filing_id ─┐ self-ref)
                 documents ──< document_chunks                                   │
                 documents ──< news (news.document_id, nullable)                 │

Financials       companies ──< financial_facts        (raw XBRL, point-in-time)
                 companies ──< financial_metrics       (computed, versioned)
                 companies ──< price_history
                 companies ──< corporate_actions

Ownership        companies ──< insider_transactions
                 companies ──< institutional_holdings

AI output        companies ──< research_reports ──< research_sources
                 research_reports ──< claim_verifications >── chat_messages
                 research_reports (supersedes_report_id ─┐ self-ref)

Users            users ──< refresh_tokens (replaced_by_id ─┐ self-ref, rotation chain)
                 users ──< watchlists ──< watchlist_items >── companies
                 users ──< alerts >── companies
                 users ──< chat_sessions ──< chat_messages
                 users ──< report_feedback >── research_reports

Operations       ingestion_runs, ingestion_dead_letters, jobs, llm_calls,
                 retrieval_logs, data_quality_issues, eval_runs ──< eval_results,
                 data_freshness
```

`──<` = one-to-many (FK on the right table). `>──` = many-to-one reference.

### Why `financial_facts` and `financial_metrics` are separate (spec §11.4, §13.4)

`financial_facts` stores raw XBRL exactly as filed — immutable, point-in-time, with
`is_amended` for restatements. `financial_metrics` stores canonical computed values with
lineage (`is_derived`, `formula_id`, `source_id`, `as_reported_accession`, `is_latest`). Keeping
them apart lets us recompute metrics, track restatements, and cite a derived number back to the
exact facts it came from without mutating source data.

## Index rationale

| Table | Index | Why |
|-------|-------|-----|
| `document_chunks` | `embedding` **HNSW** (`vector_cosine_ops`, m=16, ef_construction=64) | Approximate nearest-neighbour vector search for RAG (RAG-010, NFR-002); cosine matches Voyage embeddings (ADR-0010) |
| `document_chunks` | `tsv` **GIN** | Keyword search over the generated `tsvector`; the other half of hybrid retrieval |
| `document_chunks` | btree `(company_id, filing_type, filing_date)` | Filter candidates by company + filing before/after vector search |
| `financial_facts` | btree `(company_id, concept_tag, period_end)` | Look up a concept's value for a period when computing metrics |
| `financial_metrics` | btree `(company_id, metric_name, is_latest)` | Fetch the current value of a metric for the dashboard fast (FR-002, NFR-001) |
| `price_history` | unique `(company_id, date)` | One bar per day; makes daily upserts idempotent (NFR-014) |
| `news` | btree `published_at` | Recent-news ordering on the request path (FR/NFR-006) |
| `refresh_tokens` | btree `family_id`, unique `token_hash` | Rotation/reuse detection and O(1) token lookup (ADR-0005) |
| FKs | btree on every foreign key column | Avoids sequential scans on joins and on cascade deletes |

### Uniqueness / idempotency constraints

- `companies.cik` unique; `filings.accession_number` unique; `users.email` unique.
- `documents (company_id, content_hash)` unique — re-ingesting the same document is a no-op.
- `document_chunks (document_id, chunk_index, parser_version)` unique — safe re-chunking.
- `financial_metrics (company_id, period, metric_name, basis, as_reported_accession)` unique —
  one canonical value per as-reported period.

## ON DELETE behaviour (DB-002)

Deleting a **company** cascades to all its data (documents, filings, chunks, facts, metrics,
prices, news, ownership, reports). Deleting a **user** cascades to that user's rows (refresh
tokens, watchlists, alerts, chat, feedback) and sets `research_reports.user_id` to NULL (the
report survives as system-owned). `news.document_id`, `filings.amends_filing_id`,
`research_reports.supersedes_report_id`, and `refresh_tokens.replaced_by_id` use `SET NULL`.
User-data hard-deletion for privacy requests (LGL-007) is a Phase 4b job.

## Working with the schema

```bash
# from repo root, with Docker running
make up                                   # Postgres + Redis
cd backend
uv run alembic upgrade head               # apply migrations
uv run python ../scripts/seed.py          # 3 companies + placeholder rows (idempotent)
uv run alembic downgrade base             # tear the schema back down
```

Migrations are tested up and down, on empty and populated databases, in
`backend/tests/integration/test_migrations.py`.

### Migration history

| Revision | Change |
|----------|--------|
| `fd52b5f9aeae` | Initial schema (all 33 tables, pgvector, indexes). |
| `d5095d7bd954` | Widen `financial_facts.concept_tag` to `VARCHAR(256)` — some real XBRL element names exceed 128 chars (Phase 1a ingestion). |
| `7ce7bee338f7` | Make `financial_metrics.metric_value` nullable — a sector-inapplicable or uncomputable metric stores NULL + a reason in `quality_flags`, never a misleading zero (Phase 1c, DR-041/042). |
| `8c58e66dbdbc` | Add `document_chunks.embedding_dim` (per-row dimension beside `embedding_model`, EMB-001) and a nullable `embedding_new vector(1024)` staging column for zero-downtime model migration (Phase 2b, EMB-003, ADR-0013). |
