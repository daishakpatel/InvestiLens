#!/usr/bin/env bash
# The five-minute path against the demo build, end to end (Phase 7l Part E, NFR-ME-012):
#   scripts/vertical_slice.sh            # rebuild the demo DB, run the spec, write the GIF
#   REUSE_DB=1 scripts/vertical_slice.sh # keep the existing assay_desk_demo database
# Needs Postgres (docker compose up -d postgres). Uses ports 8010 (API) and 5180 (frontend) so a
# running dev stack on 8000/5173 is left alone. Never touches the dev database.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
logs="$(mktemp -d)"
api_pid="" preview_pid=""
cleanup() {
  [[ -n "$api_pid" ]] && kill "$api_pid" 2>/dev/null || true
  [[ -n "$preview_pid" ]] && kill "$preview_pid" 2>/dev/null || true
}
trap cleanup EXIT

cd "$root/backend"
if [[ -z "${REUSE_DB:-}" ]]; then
  uv run python ../scripts/demo_db.py
fi
demo_db=$(uv run python -c "import sys; sys.path.insert(0, '../scripts')
from _dbtools import with_database
from app.config import get_settings
print(with_database(get_settings().database_url, 'assay_desk_demo'))")

# The API exactly as render.yaml configures it, on the local demo database.
DEMO_MODE=true DATABASE_URL="$demo_db" PROVIDER_MODE=mock BACKGROUND_JOBS_ENABLED=false \
  REFRESH_PRICES_ON_STARTUP=false RATE_LIMIT_PER_MINUTE=300 \
  uv run uvicorn app.main:app --port 8010 >"$logs/api.log" 2>&1 &
api_pid=$!

cd "$root/frontend"
npm run build >"$logs/build.log"
VITE_DEV_PROXY_TARGET=http://localhost:8010 npx vite preview --port 5180 --strictPort \
  >"$logs/preview.log" 2>&1 &
preview_pid=$!

DEMO_API_URL=http://localhost:8010 SMOKE_TIMEOUT_SECONDS=60 "$root/scripts/smoke_demo.sh"

cd "$root/e2e"
rm -rf test-results/vertical-slice
E2E_BASE_URL=http://localhost:5180 DEMO_DATABASE_URL="$demo_db" \
  npx playwright test tests/vertical-slice.spec.ts --reporter=line

cd "$root/backend"
uv run python ../scripts/make_demo_gif.py
echo "vertical slice passed; logs in $logs"
