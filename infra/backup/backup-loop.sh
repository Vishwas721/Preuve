#!/bin/sh
# Daily database backups for the production stack (Phase 5D).
# Runs in the `backup` service (postgres image): a dump at start-up if none exists yet, then one a
# day at BACKUP_HOUR (UTC), keeping BACKUP_KEEP_DAYS days. `backup.sh` in infra/scripts triggers
# one on demand by running `backup-loop.sh once`.
set -eu

KEEP="${BACKUP_KEEP_DAYS:-14}"
HOUR="${BACKUP_HOUR:-3}"

dump() {
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  tmp="/backups/.preuve-${stamp}.sql.gz.part"
  out="/backups/preuve-${stamp}.sql.gz"
  # Plain SQL, no owners/privileges, so it restores into any database; gzip to save space.
  pg_dump --no-owner --no-privileges --clean --if-exists | gzip -9 > "$tmp"
  mv "$tmp" "$out"   # only complete dumps get the final name
  find /backups -name 'preuve-*.sql.gz' -mtime "+${KEEP}" -delete
  echo "backup: wrote $(basename "$out") ($(du -h "$out" | cut -f1)); keeping ${KEEP} days"
}

if [ "${1:-}" = "once" ]; then
  dump
  exit 0
fi

ls /backups/preuve-*.sql.gz >/dev/null 2>&1 || dump
while true; do
  now=$(date -u +%s)
  next=$(date -u -d "$(date -u +%Y-%m-%d) ${HOUR}:00:00" +%s 2>/dev/null || echo $((now + 86400)))
  [ "$next" -le "$now" ] && next=$((next + 86400))
  sleep $((next - now))
  dump || echo "backup: FAILED at $(date -u)" >&2
done
