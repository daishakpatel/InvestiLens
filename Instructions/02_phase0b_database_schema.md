# Phase 0b — Database Schema & Migrations

**Prerequisites:** `01_phase0a_architecture_and_adrs.md` done (repo skeleton + ADR-0001 exist).
**Blocks:** every ingestion, metrics, RAG, and API task file — they all write to or read from
this schema.
**Full spec sections:** §23 (full database schema — this file is the actionable version of
it), §11 (financial data correctness rules — several tables exist *because* of these rules).

## Objective

Stand up PostgreSQL 16 + pgvector, create every table needed for the full MVP (even ones later
phases will populate), write Alembic migrations, and produce a seed script.

## Scope

1. **Set up Postgres 16 + pgvector** in `docker-compose.yml`, plus Alembic wired to
   `backend/app/models/`.
2. **Create all tables below** as SQLAlchemy models + one initial migration. Build the whole
   schema now even though most tables are empty until later phases — this avoids painful
   migrations later. Use `NUMERIC` for money, never `FLOAT`.

   **Reference / company:**
   `companies`, `company_identifiers`, `fiscal_calendars`

   **Documents & filings:**
   `documents` (unified registry — filings, earnings releases, transcripts, news, IR
   materials all point here), `filings`, `document_chunks`

   **Financial data:**
   `financial_facts` (raw XBRL, point-in-time), `financial_metrics` (canonical computed
   values), `price_history`, `corporate_actions`

   **News & ownership:**
   `news`, `insider_transactions`, `institutional_holdings`

   **AI output:**
   `research_reports`, `research_sources`, `claim_verifications`

   **Users:**
   `users`, `refresh_tokens`, `watchlists`, `watchlist_items`, `alerts`, `chat_sessions`,
   `chat_messages`, `report_feedback`

   **Operations:**
   `ingestion_runs`, `ingestion_dead_letters`, `jobs`, `llm_calls`, `retrieval_logs`,
   `data_quality_issues`, `eval_runs`, `eval_results`, `data_freshness`

   Get the exact column lists from spec §23.1–23.3 — copy them faithfully, they're already
   finalized. Key things not to skip:
   - `financial_facts` and `financial_metrics` are **separate tables** — raw XBRL vs computed/
     derived values. Don't collapse them.
   - `financial_metrics` needs `is_derived`, `formula_id`, `source_id`, `as_reported_accession`,
     `is_latest` — these support point-in-time correctness (spec §11.4) and citation lineage
     (spec §13.4).
   - `document_chunks` needs `chunk_type` (`text|table|xbrl_note`), `char_start`/`char_end`,
     `parent_section_id`, a generated `tsv tsvector` column, and both an HNSW index on
     `embedding` and a GIN index on `tsv`.
   - `page` is nullable everywhere and populated **only** for PDF-sourced content (spec §13.3
     — HTML filings have no real pages).
3. **Constraints:** `UNIQUE(cik)` on companies, `UNIQUE(accession_number)` on filings,
   `UNIQUE(company_id, date)` on price_history, `UNIQUE(company_id, content_hash)` on
   documents. Foreign keys enforced everywhere; document `ON DELETE` behavior per table.
4. **Migration tests:** upgrade and downgrade against an empty DB and against a populated one.
5. **Seed script** (`scripts/seed.py`): inserts 3 companies (NVDA, AAPL, JPM — JPM specifically
   because it exercises the "not applicable for banks" sector rules later) with placeholder
   rows in each table so downstream agents can run queries immediately, even before real
   ingestion exists.
6. **`docs/database.md`**: ERD (can be a generated image or a clear ASCII table list) plus a
   short rationale for each index.

## Out of scope for this file

Don't populate real data (that's Phase 1). Don't write the finance formulas (Phase 1c). Don't
build the vector/keyword search *logic* (Phase 2b) — just the columns and indexes that logic
will use.

## Definition of Done

- [ ] All ~30 tables exist as SQLAlchemy models with an initial Alembic migration
- [ ] Migration passes up/down tests on empty and populated DB
- [ ] HNSW index on `document_chunks.embedding`, GIN index on `document_chunks.tsv`
- [ ] `NUMERIC` used for every monetary column — grep confirms no `Float` in financial columns
- [ ] `scripts/seed.py` runs and produces 3 companies with placeholder rows in every table
- [ ] `docs/database.md` exists with ERD + index rationale
