.PHONY: install lint typecheck test check coverage up down openapi seed eval worker beat backup

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

# Seed a demo-ready DB for the seed tickers (mock pipeline + FakeLLM reports). Part of the
# fresh-clone → running-dashboard path (NFR-012, scope #12).
seed:
	cd backend && uv run python ../scripts/seed_demo.py --with-reports

# Evaluation smoke run (§18.4, Phase 5b). Full/gate variants: see scripts/run_eval.py.
eval:
	cd backend && uv run python ../scripts/run_eval.py --smoke

# Run all three Celery queues in one dev worker (prod runs one worker per queue — see compose).
# --pool solo avoids the macOS prefork fork-safety crash in local dev; Linux containers
# (docker-compose / Render) use the default prefork pool with real per-queue concurrency.
worker:
	cd backend && uv run celery -A app.tasks.celery_app worker -Q interactive,ingestion,batch --pool solo --loglevel=info

# Celery Beat scheduler (the daily pipeline + pollers + alert dispatch).
beat:
	cd backend && uv run celery -A app.tasks.celery_app beat --loglevel=info

# Back up the dev DB (pg_dump custom format). Restore: scripts/restore_db.sh <dump>.
backup:
	mkdir -p backups
	docker compose exec -T postgres pg_dump -Fc --no-owner --no-privileges -U $${POSTGRES_USER:-investilens} $${POSTGRES_DB:-investilens} > backups/investilens-$$(date -u +%Y%m%dT%H%M%SZ).dump
