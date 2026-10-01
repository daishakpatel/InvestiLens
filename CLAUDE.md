# InvestiLens — Agent Instructions

## Workflow

- Work is driven by sequential task files in `Instructions/`. Start with
  `Instructions/00_START_HERE.md`, and do **one task file per session**, in order.
- Don't start a task whose Prerequisites aren't done. Don't mark a task done until every item
  in its Definition of Done is checked.
- "The full spec" means `docs/InvestiLens_Spec_v2.md`. Read only the sections the task file
  cites, not the whole document.
- Need a decision the task file doesn't make? Check `docs/decisions/` first. If it isn't
  decided yet, make the call, write a one-paragraph ADR using
  `docs/decisions/0000-adr-template.md`, and continue. Don't block on it.

## Global conventions

@docs/conventions.md

## Commands

- `make check`: backend ruff + mypy (strict) + pytest, frontend eslint + tsc. Must pass before a
  task is done.
- Backend uses `uv` (`cd backend && uv run ...`). Frontend uses npm (`cd frontend && npm run ...`).
