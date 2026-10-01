# Agent Guide

Read this before changing anything. Rules everyone follows are in
[conventions.md](conventions.md). How the system fits together is in
[architecture.md](architecture.md).

## Where contracts live

A contract is anything another module or agent builds against.

| Contract | Location | Created in |
|----------|----------|-----------|
| Architecture & decisions | `docs/architecture.md`, `docs/decisions/` | Phase 0a |
| Database schema | `docs/database.md`, `infrastructure/migrations/` (Alembic) | Phase 0b |
| HTTP API | `docs/api.md`, `docs/openapi.json` | Phase 0c |
| Shared Pydantic schemas (report, source records, metric results) | `backend/app/schemas/` | Phase 0c |
| Provider interfaces + mocks | `backend/app/providers/` | Phase 0d |

## The contract rule

**Breaking a contract requires an ADR** in `docs/decisions/` (use
[0000-adr-template.md](decisions/0000-adr-template.md)), a version bump, and an update to every
consumer in the same PR. Breaking changes include removing or renaming a field, changing a
type or unit, or changing an endpoint's semantics. Additive changes (new optional fields, new
endpoints) don't need an ADR, but they still update the matching doc in the same PR.

## Fixtures (offline development)

The frozen fixture dataset lives in `backend/tests/fixtures/` (built in Phase 0d): NVDA, AAPL,
and JPM filings HTML, XBRL facts, price history, a news sample, recorded LLM responses, and
`golden_metrics.json`. Every provider has a mock backed by these fixtures, so development and
CI need no network access or API keys. The golden question set for evals lives in
`backend/tests/eval/`.

## Before you open a PR

- `make check` passes (lint, format, type-check, tests). CI runs the same gates.
- Docs match the code (schema, API, and DB changes documented in the same PR).
- `.github/CODEOWNERS` says who approves the paths you touched.
