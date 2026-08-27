#!/usr/bin/env bash
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/postgres-connection.sh
source "$SCRIPT_DIR/lib/postgres-connection.sh"

BACKUP_DATABASE_URL="${ZWORKFORCE_BACKUP_DATABASE_URL:-${ZWORKFORCE_DATABASE_URL:-}}"
if [[ -z "$BACKUP_DATABASE_URL" ]]; then
  echo "ZWORKFORCE_DATABASE_URL or ZWORKFORCE_BACKUP_DATABASE_URL is required" >&2
  exit 2
fi

for command in pg_dump pg_restore sha256sum; do
  command -v "$command" >/dev/null 2>&1 || { echo "$command is required" >&2; exit 2; }
done

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="${ZWORKFORCE_BACKUP_DIR:-./backups}"
OUTPUT="${1:-${BACKUP_DIR}/zworkforce-${STAMP}.dump}"
mkdir -p "$(dirname "$OUTPUT")"

TMP="${OUTPUT}.partial"
rm -f "$TMP"
# Prefer a direct or session-pooler URL for pg_dump. Transaction poolers can
# recycle connections between the catalog and data phases of a dump.
postgres_configure_service "$BACKUP_DATABASE_URL"
unset BACKUP_DATABASE_URL ZWORKFORCE_BACKUP_DATABASE_URL
trap 'postgres_cleanup_service; rm -f -- "$TMP"' EXIT

pg_dump \
  --format=custom \
  -Z 9 \
  --no-owner \
  --no-acl \
  --file "$TMP" \
  --dbname=service=zworkforce

# A backup is not accepted until pg_restore can parse its catalog.
pg_restore --list "$TMP" >/dev/null
mv "$TMP" "$OUTPUT"
sha256sum "$OUTPUT" > "${OUTPUT}.sha256"

printf 'backup=%s\nchecksum=%s\n' "$OUTPUT" "${OUTPUT}.sha256"
