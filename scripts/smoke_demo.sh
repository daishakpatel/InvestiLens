#!/usr/bin/env bash
# Post-deploy smoke test for the public demo (Phase 7l, NFR-ME-009, ADR-0050).
#   DEMO_API_URL=https://investilens-api.onrender.com scripts/smoke_demo.sh
# Waits for the health endpoint, then checks the deployment really is the locked-down demo:
# demo mode on and registration closed.
set -euo pipefail

api="${DEMO_API_URL:?set DEMO_API_URL to the API origin, e.g. https://investilens-api.onrender.com}"
deadline=$((SECONDS + ${SMOKE_TIMEOUT_SECONDS:-600}))

until curl -fsS --max-time 10 "$api/api/v1/health" 2>/dev/null | grep -q '"ok"'; do
  if ((SECONDS >= deadline)); then
    echo "smoke: $api/api/v1/health never answered ok" >&2
    exit 1
  fi
  sleep 10
done

if ! curl -fsS --max-time 10 "$api/api/v1/meta/demo" | grep -q '"enabled":true'; then
  echo "smoke: demo mode is off at $api" >&2
  exit 1
fi

code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -X POST \
  -H 'content-type: application/json' \
  -d '{"email":"smoke@example.com","password":"smoke-test-password"}' \
  "$api/api/v1/auth/register")
if [[ "$code" != "403" ]]; then
  echo "smoke: registration should be closed in the demo (got HTTP $code)" >&2
  exit 1
fi

echo "smoke: demo at $api is healthy, in demo mode, with registration closed"
