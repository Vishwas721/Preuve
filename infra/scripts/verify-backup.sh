#!/usr/bin/env bash
# Prove the latest backup restores (Phase 5D): load it into a scratch database next to the live
# one and compare row counts of every table. Doesn't touch live data.
#
#   infra/scripts/verify-backup.sh [backup .sql.gz]   # default: the newest in BACKUP_DIR
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

DIR="$(env_value BACKUP_DIR ../backups)"
case "$DIR" in /*|[A-Za-z]:*) ;; *) DIR="$INFRA_DIR/$DIR" ;; esac
DUMP="${1:-$(ls -1t "$DIR"/preuve-*.sql.gz 2>/dev/null | head -1 || true)}"
[ -n "$DUMP" ] && [ -f "$DUMP" ] || { echo "No backup found in $DIR" >&2; exit 1; }
echo "Verifying $(basename "$DUMP")…"

psql_live() { compose exec -T postgres sh -c "psql -At -U \"\$POSTGRES_USER\" -d $1 -c \"$2\""; }

compose exec -T postgres sh -c 'dropdb -U "$POSTGRES_USER" --if-exists preuve_verify && createdb -U "$POSTGRES_USER" preuve_verify'
gunzip -c "$DUMP" | compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d preuve_verify' >/dev/null

# Exact counts (n_live_tup is an estimate): build one count(*) per table.
TABLES="$(psql_live preuve_verify "select string_agg(quote_ident(tablename), ' ') from pg_tables where schemaname='public'")"
mismatch=0
for t in $TABLES; do
  a="$(psql_live preuve_verify "select count(*) from $t")"
  b="$(psql_live "\$POSTGRES_DB" "select count(*) from $t")"
  if [ "$a" != "$b" ]; then
    echo "  $t: backup $a, live $b"
    mismatch=1
  fi
done
version_backup="$(psql_live preuve_verify 'select version_num from alembic_version')"
compose exec -T postgres sh -c 'dropdb -U "$POSTGRES_USER" preuve_verify'
echo "  $(echo "$TABLES" | wc -w | tr -d ' ') tables restored, schema revision $version_backup"
if [ "$mismatch" = 1 ]; then
  echo "Row counts differ (expected only if data changed since the backup was taken)." >&2
  exit 3
else
  echo "OK: the backup restores and matches the live row counts."
fi
