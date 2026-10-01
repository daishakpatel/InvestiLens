# ADR-0001: Modular monolith, not microservices

- **Status:** Accepted
- **Date:** 2026-09-28
- **Spec refs:** §19.3, §19.4

## Problem

The system spans many domains (company data, filings, financials, news, RAG, research, chat,
auth, watchlists) and needs background work for ingestion and report generation. Microservices
would add network hops, distributed transactions, per-service deploys, and ops overhead that a
single-maintainer MVP can't justify.

## Decision

Ship one FastAPI deployable plus Celery workers from the same codebase, sharing one PostgreSQL
and one Redis. Keep strict module boundaries: modules talk through service interfaces, and no
module touches another module's tables except through that module's repository. Layering is
`api → services → repositories → models`. `finance/`, `rag/`, `ingestion/`, `citation/`, and
`tasks/` are libraries used by services.

## Consequences

One build, one deploy, simple local dev (`docker compose up`), and in-process calls without
network overhead. Boundaries are enforced by review and layering rules, not by the network, so
discipline matters. If one module later needs independent scaling (most likely embedding and
ingestion workers), its service interface is already the seam to split along.
