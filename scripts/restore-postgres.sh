#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/postgres-connection.sh
source "$SCRIPT_DIR/lib/postgres-connection.sh"

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <backup.dump>" >&2
  exit 2
fi
RESTORE_DATABASE_URL="${ZWORKFORCE_RESTORE_DATABASE_URL:-${ZWORKFORCE_DATABASE_URL:-}}"
if [[ -z "$RESTORE_DATABASE_URL" ]]; then
  echo "ZWORKFORCE_DATABASE_URL or ZWORKFORCE_RESTORE_DATABASE_URL is required" >&2
  exit 2
fi
if [[ "${ZWORKFORCE_RESTORE_CONFIRM:-}" != "YES" ]]; then
  echo "refusing restore: set ZWORKFORCE_RESTORE_CONFIRM=YES after stopping API/workers/schedulers/outbox" >&2
  exit 2
fi

for command in pg_restore sha256sum; do
  command -v "$command" >/dev/null 2>&1 || { echo "$command is required" >&2; exit 2; }
done

BACKUP="$1"
[[ -f "$BACKUP" ]] || { echo "backup not found: $BACKUP" >&2; exit 2; }

if [[ -f "${BACKUP}.sha256" ]]; then
  sha256sum -c "${BACKUP}.sha256"
else
  echo "warning: checksum sidecar ${BACKUP}.sha256 not found" >&2
fi

# Validate the archive before touching the target database.
pg_restore --list "$BACKUP" >/dev/null

postgres_configure_service "$RESTORE_DATABASE_URL"
unset RESTORE_DATABASE_URL ZWORKFORCE_RESTORE_DATABASE_URL
trap postgres_cleanup_service EXIT

pg_restore \
  --exit-on-error \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  --dbname=service=zworkforce \
  "$BACKUP"

echo "restore completed; run zworkforce doctor and scripts/smoke-test.sh before resuming traffic"
