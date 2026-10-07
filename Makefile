.PHONY: install lint typecheck test check coverage up down openapi

install:
	cd backend && uv sync
	cd frontend && npm ci

lint:
	cd backend && uv run ruff check . ../scripts && uv run ruff format --check . ../scripts
	cd frontend && npm run lint

typecheck:
	cd backend && uv run mypy
	cd frontend && npm run typecheck

test:
	cd backend && uv run pytest
	cd frontend && npm run test

check: lint typecheck test

# Coverage gate (DoD / NFR-013, ADR-0019): one measured run, two hard thresholds —
# >=80% overall and 100% on the finance + citation modules. Needs Postgres for the
# integration tests (finance/builder.py + citation/resolver.py are DB-backed).
coverage:
	cd backend && uv run pytest --cov=app --cov-report=term-missing
	cd backend && uv run coverage report --fail-under=80
	cd backend && uv run coverage report --include="app/finance/*,app/citation/*" --fail-under=100

# Regenerate the API contract: OpenAPI spec + TypeScript client. Run after changing routes/schemas.
openapi:
	cd backend && uv run python ../scripts/export_openapi.py
	cd frontend && node_modules/.bin/openapi-typescript ../docs/openapi.json -o src/services/api.d.ts

up:
	docker compose up -d

down:
	docker compose down
