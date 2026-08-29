#!/usr/bin/env bash
set -Eeuo pipefail
: "${BACKUP_CREATE_COMMAND:?BACKUP_CREATE_COMMAND is required}"
: "${BACKUP_RESTORE_COMMAND:?BACKUP_RESTORE_COMMAND is required}"
: "${BACKUP_VERIFY_COMMAND:?BACKUP_VERIFY_COMMAND is required}"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT
export PHASE6_BACKUP_WORKDIR="$WORKDIR"
bash -lc "$BACKUP_CREATE_COMMAND"
bash -lc "$BACKUP_RESTORE_COMMAND"
bash -lc "$BACKUP_VERIFY_COMMAND"
echo "external backup restore verified"
