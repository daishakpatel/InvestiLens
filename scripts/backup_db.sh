#!/usr/bin/env bash
# Database backup (Phase 5d, scope #11). Writes a compressed custom-format dump of DATABASE_URL.
#
# Custom format (-Fc) so restore_db.sh can use pg_restore with parallelism and selective restore.
# In production this runs as a scheduled job (daily) against the managed Postgres; the dump is
# uploaded to versioned object storage alongside the raw filings (ADR-0012). Locally, pg_dump
# lives in the postgres container, so run it through compose:
#
#   docker compose exec -T postgres pg_dump -Fc "$DATABASE_URL" > backups/investilens-$(date +%F).dump
#
# or, with pg client tools on PATH (CI / managed host):
#
#   DATABASE_URL=postgresql://... scripts/backup_db.sh
set -euo pipefail

: "${DATABASE_URL:?set DATABASE_URL (postgresql://... ; strip any +psycopg driver suffix)}"
OUT_DIR="${BACKUP_DIR:-backups}"
mkdir -p "$OUT_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$OUT_DIR/investilens-$STAMP.dump"

# Normalize a SQLAlchemy URL (postgresql+psycopg://) to a libpq URL pg_dump understands.
PG_URL="${DATABASE_URL/+psycopg/}"

echo "Dumping $PG_URL -> $OUT"
pg_dump -Fc --no-owner --no-privileges "$PG_URL" -f "$OUT"
echo "Wrote $OUT ($(du -h "$OUT" | cut -f1))"
