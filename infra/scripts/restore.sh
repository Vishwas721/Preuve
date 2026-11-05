#!/usr/bin/env bash
# Restore a backup into the production database (Phase 5D). Destructive: replaces current data.
#
#   infra/scripts/restore.sh backups/preuve-20261105T030000Z.sql.gz [--yes]
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

DUMP="${1:?usage: restore.sh <backup .sql.gz> [--yes]}"
[ -f "$DUMP" ] || { echo "No such file: $DUMP" >&2; exit 1; }
if [ "${2:-}" != "--yes" ]; then
  read -r -p "Replace ALL current Preuve data with $(basename "$DUMP")? Type 'restore': " answer
  [ "$answer" = "restore" ] || { echo "Cancelled."; exit 1; }
fi

echo "Taking a safety backup of the current data first…"
compose exec -T backup sh /usr/local/bin/backup-loop.sh once
echo "Stopping the app…"
compose stop web worker api
echo "Restoring $(basename "$DUMP")…"
gunzip -c "$DUMP" | compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
echo "Running migrations (the dump may be from an older version)…"
compose run --rm migrate
compose up -d api worker web
wait_healthy api 180
echo "Restored."
