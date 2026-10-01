.PHONY: install lint typecheck test check up down openapi

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

check: lint typecheck test

# Regenerate the API contract: OpenAPI spec + TypeScript client. Run after changing routes/schemas.
openapi:
	cd backend && uv run python ../scripts/export_openapi.py
	cd frontend && node_modules/.bin/openapi-typescript ../docs/openapi.json -o src/services/api.d.ts

up:
	docker compose up -d

down:
	docker compose down
