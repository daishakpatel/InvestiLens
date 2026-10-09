# InvestiLens backend image (Phase 5d). Serves the API and runs the Celery workers/beat — one
# image, different commands (compose/render set the command per service).
FROM python:3.12-slim AS base

# uv for fast, locked installs (matches local/CI; see ADR-0024).
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# pg client tools (pg_dump/pg_restore) for the backup/restore scripts; curl for healthchecks.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first (cached layer) from the lockfile — reproducible, no dev deps in the image.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

# App code + migrations (migrations live one level up in the repo).
COPY backend/ ./
COPY infrastructure/ ../infrastructure/
RUN uv sync --locked --no-dev

EXPOSE 8000

# Default command = API. Workers/beat override this (see docker-compose.yml / render.yaml).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
