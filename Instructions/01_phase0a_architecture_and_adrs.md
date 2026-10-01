# Phase 0a — Architecture & ADRs

**Prerequisites:** none — this is the first file.
**Blocks:** everything else. Nothing else starts until this is merged.
**Full spec sections:** §2 (vision/principles), §3 (users), §4 (scope), §19 (architecture),
§20 (stack), §33.1 (contract-first protocol), Appendix F (open decisions).

## Objective

Produce the foundational documents every other task file and every other agent will build
against: the architecture doc, the ADRs for decisions that shape everything downstream, and
the repo skeleton.

## Scope

1. **Repo skeleton.** Create the structure below (empty folders/`__init__.py`/`.gitkeep` where
   needed — don't build features yet):
   ```text
   investilens/
   ├── frontend/src/{components,pages,hooks,services,types,charts}
   ├── backend/app/{api,models,schemas,services,repositories,finance,providers,rag,citation,ingestion,tasks,utils}
   ├── backend/tests/{unit,integration,fixtures,eval}
   ├── infrastructure/{docker,migrations,terraform}
   ├── docs/decisions/
   ├── scripts/
   ├── .github/workflows/
   ├── docker-compose.yml, Makefile, README.md, .env.example
   ```
2. **`docs/architecture.md`** — one-page system diagram (ASCII is fine) plus a short
   explanation of the core separation: deterministic finance layer → retrieval → LLM →
   citation validator → report. Reuse the diagram from spec §19.2 verbatim; it's the
   project's central idea and should not be reworded.
3. **Modular monolith decision.** Single FastAPI deployable + Celery workers, not
   microservices, for MVP (spec §19.3). Write this as ADR-0001.
4. **Write these ADRs** (`docs/decisions/000N-title.md`, one paragraph problem + decision +
   consequences each — don't over-write these, they're meant to be quick):
   - ADR-0001: Modular monolith vs microservices
   - ADR-0002: pgvector vs a dedicated vector database (decision: pgvector for MVP, spec §20)
   - ADR-0003: Custom RAG orchestration vs LangChain (decision: custom, spec §20)
   - ADR-0004: Citation anchors instead of page numbers for HTML filings (spec §13.3 — record
     *why*: SEC filings are HTML with no stable pagination)
   - ADR-0005: JWT + rotating refresh token strategy (spec §26.1)
   - ADR-0006: Anonymous access policy — decide now whether unauthenticated users get any
     read access or AI quota (spec Appendix F item 5)
5. **Pick and record data providers** (spec §7, Appendix F items 1–4). You must choose
   concrete providers, not leave "Market API" as a placeholder:
   - Filings/XBRL: SEC EDGAR (fixed choice, free, no ADR needed)
   - Price provider: pick one (e.g. Tiingo, Polygon, Financial Modeling Prep) — write ADR-0007
     with cost tier and rate limits
   - News provider: pick one — write ADR-0008
   - LLM: OpenAI (or your choice) — write ADR-0009, include model names for "cheap" (routing,
     classification) and "strong" (report synthesis) tiers
   - Embeddings: pick a model + dimension — write ADR-0010
   - Decide now: are transcripts in MVP scope, or deferred to Phase 2? (Appendix F item 2) —
     record the decision in ADR-0009 or a new one.
6. **`docs/agent-guide.md`** — a half-page explaining: where contracts live, the rule that
   breaking a contract requires an ADR, and where to find the fixture dataset (built in
   Phase 0d).
7. **CODEOWNERS** — even with few contributors, map top-level folders to whoever owns them,
   so it's clear who approves changes to `backend/app/finance/` vs `frontend/src/`.

## Out of scope for this file

Don't write actual ingestion, parsing, or API code — that's later phases. Don't design the
database schema in detail — that's Phase 0b (you can sketch table *names* in the architecture
doc, no columns).

## Definition of Done

- [ ] Repo skeleton exists and builds/lints with nothing in it (empty CI passes)
- [ ] `docs/architecture.md` has the diagram and a plain-English walkthrough of "life of a
      research request"
- [ ] ADR-0001 through ADR-0010 exist, each with problem/decision/consequences
- [ ] Every data provider has a name, not a placeholder
- [ ] `docs/agent-guide.md` and `CODEOWNERS` exist
- [ ] Anonymous access policy is explicitly decided (yes/no, and what's allowed if yes)
