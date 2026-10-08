# InvestiLens

AI-powered investment research platform. Deterministic financial data from SEC filings and
market sources, combined with retrieval-grounded LLM analysis in which every claim is cited
to a verifiable source.

> **Status:** Phase 0 (contracts) in progress. Architecture and ADRs done.

## Project overview

InvestiLens is a full-stack financial intelligence application for researching public
companies. It combines deterministic financial calculations with SEC filings, market data,
news, retrieval-augmented generation, and citation validation so generated research can be
traced back to its evidence.

### Language profile

| Language | Approx. share of tracked source bytes | Main use |
|----------|---------------------------------------|----------|
| Python | 76.4% | FastAPI backend, finance, ingestion, RAG, evaluation, and tests |
| TypeScript / TSX | 22.4% | React frontend, typed API client, and UI tests |
| JavaScript, CSS, HTML, YAML | 1.2% | Tooling, styling, markup, configuration, and infrastructure |

The percentages above are a local source-size snapshot. The language bar shown by GitHub is
calculated automatically by GitHub Linguist and may differ because it applies its own rules for
generated files, fixtures, documentation, and vendored content.

### What is included

- **Backend:** Python 3.12, FastAPI, Celery, PostgreSQL 16, pgvector, Redis, and deterministic
	financial metrics.
- **Frontend:** React, TypeScript, Vite, and a typed API client for the research dashboard.
- **AI and data:** SEC EDGAR, Tiingo, Finnhub, Anthropic Claude, Voyage AI embeddings, hybrid
	retrieval, and source-validated citations.
- **Engineering focus:** contract-first APIs, offline mock providers, reproducible evaluation,
	observability, security hardening, and an explicit educational-use disclaimer.

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

## Evaluation & quality

Quality is measured against a 100+ question golden set (`backend/tests/eval/golden_v0.jsonl`,
categories per spec §18.1) by the harness in `backend/app/eval/`. CI fails a PR that regresses
citation accuracy (> 1 pt), Recall@5 (> 2 pts), or hallucination rate (> 0.5 pts) vs the baseline
(EVAL-002). See `docs/testing.md` and [ADR-0020](docs/decisions/0020-evaluation-framework.md).

| Metric | Baseline | Mode |
|--------|----------|------|
| Citation accuracy | 1.00 | measured (deterministic, offline) |
| Hallucination rate | 0.00 | measured (deterministic, offline) |
| Abstention accuracy | 1.00 | measured (deterministic, offline) |
| Numeric answer accuracy | 1.00 | measured (deterministic, offline) |
| Recall@5 | _pending_ | needs live Voyage embeddings (ADR-0010) |
| Qualitative faithfulness (LLM-judge ≥ 0.85 agreement) | _pending_ | needs an LLM key (ADR-0009) |
| Cost / latency per report & chat | _pending_ | needs a live run |

Deterministic metrics are measured in the default mock mode (hash embeddings + Fake LLM), so
numeric accuracy, abstention, citation accuracy, and hallucination are real numbers; Recall@K and
judge faithfulness only become meaningful with live Voyage + an LLM key and are marked _pending_
until that run — the resume bullets should cite the measured rows, not the pending ones. Reproduce
with `make coverage` (gates) and `uv run python ../scripts/run_eval.py` (full set).

## Disclaimer

InvestiLens provides research information for educational purposes only and is not
investment, legal, or tax advice.
