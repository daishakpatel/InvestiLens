# InvestiLens

AI-powered investment research platform. Deterministic financial data from SEC filings and
market sources, combined with retrieval-grounded LLM analysis in which every claim is cited
to a verifiable source.

> **Status:** Phase 0 (contracts) in progress. Architecture and ADRs done.

## Core principle

The LLM is not the source of truth. Financial numbers are computed in code. The LLM only
summarizes and explains retrieved evidence, and the backend validates every citation before
it is shown.

## Repository guide

| Path | Purpose |
|------|---------|
| `docs/architecture.md` | System design and the life of a research request |
| `docs/agent-guide.md` | Where contracts live and how to change them |
| `docs/InvestiLens_Spec_v2.md` | Full product & technical specification (reference) |
| `docs/conventions.md` | Global rules for every change (money, dates, AI, external calls) |
| `docs/decisions/` | Architecture Decision Records (ADRs) |
| `Instructions/` | Sequential, agent-sized task files. Start at `00_START_HERE.md` |
| `backend/` | FastAPI app, Celery workers, data pipeline (Python 3.12, uv) |
| `frontend/` | React + TypeScript SPA (Vite) |
| `infrastructure/` | Docker, Alembic migrations, Terraform |

## How we build

1. Work through `Instructions/` in order, one task file at a time.
2. Each task's Definition of Done must be fully met before the next starts.
3. Unmade decisions become a short ADR in `docs/decisions/`, not a blocker.
4. Schema, API, and DB changes update their docs in the same PR.

## Stack

Python 3.12 · FastAPI · PostgreSQL 16 + pgvector · Redis · Celery · React + TypeScript ·
Anthropic Claude · Voyage AI embeddings · SEC EDGAR · Tiingo · Finnhub. Rationale for each is in
`docs/decisions/`.

## Local setup

Prerequisites: Python 3.12, [uv](https://docs.astral.sh/uv/), Node 22+, Docker.

```bash
cp .env.example .env    # fill in POSTGRES_PASSWORD and any API keys you have
make install            # backend deps (uv) + frontend deps (npm)
make up                 # Postgres + Redis
make check              # lint, format, type-check, tests
```

API keys are optional for development. Every external provider has an offline mock (Phase 0d).

## Disclaimer

InvestiLens provides research information for educational purposes only and is not
investment, legal, or tax advice.
