#!/usr/bin/env bash
# Database restore (Phase 5d, scope #11). Restores a dump produced by backup_db.sh into
# RESTORE_DATABASE_URL (defaults to DATABASE_URL). The restore procedure is documented and tested
# — see docs/costs.md / the Phase 5d summary for a verified round-trip.
#
#   scripts/restore_db.sh backups/investilens-20261008T000000Z.dump
#
# WARNING: --clean drops existing objects in the target first. Point RESTORE_DATABASE_URL at the
# restore target (a fresh DB for a drill, or the real one for a genuine recovery) — never guess.
set -euo pipefail

DUMP="${1:?usage: restore_db.sh <dump-file>}"
: "${DATABASE_URL:?set DATABASE_URL}"
TARGET="${RESTORE_DATABASE_URL:-$DATABASE_URL}"
PG_URL="${TARGET/+psycopg/}"

echo "Restoring $DUMP -> $PG_URL"
pg_restore --clean --if-exists --no-owner --no-privileges -d "$PG_URL" "$DUMP"
echo "Restore complete. Run 'alembic current' to confirm the schema head."
