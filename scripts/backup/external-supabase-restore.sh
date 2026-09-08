#!/usr/bin/env bash
set -Eeuo pipefail

required=(
  SUPABASE_URL
  SUPABASE_SECRET_KEY
  SUPABASE_BACKUP_BUCKET
  SUPABASE_BACKUP_PREFIX
  BACKUP_ENCRYPTION_KEY
  BACKUP_SOURCE_URL
  BACKUP_RESTORE_URL
  BACKUP_VERIFY_URL
)
for name in "${required[@]}"; do
  [[ -n "${!name:-}" ]] || { echo "Missing required input: $name" >&2; exit 1; }
done

for command in curl jq openssl sha256sum; do
  command -v "$command" >/dev/null 2>&1 || { echo "Required command not found: $command" >&2; exit 1; }
done

[[ "$SUPABASE_URL" == https://* ]] || { echo "SUPABASE_URL must use HTTPS" >&2; exit 1; }
[[ "$BACKUP_SOURCE_URL" == https://* ]] || { echo "BACKUP_SOURCE_URL must use HTTPS" >&2; exit 1; }
[[ "$BACKUP_RESTORE_URL" == https://* ]] || { echo "BACKUP_RESTORE_URL must use HTTPS" >&2; exit 1; }
[[ "$BACKUP_VERIFY_URL" == https://* ]] || { echo "BACKUP_VERIFY_URL must use HTTPS" >&2; exit 1; }
[[ "$SUPABASE_BACKUP_BUCKET" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "Invalid backup bucket" >&2; exit 1; }
[[ "$SUPABASE_BACKUP_PREFIX" =~ ^[A-Za-z0-9._/-]+$ ]] || { echo "Invalid backup prefix" >&2; exit 1; }

workdir="$(mktemp -d)"
cleanup() { rm -rf "$workdir"; }
trap cleanup EXIT

urlencode() {
  jq -rn --arg value "$1" '$value|@uri'
}

supabase_storage_url() {
  local object="$1"
  printf '%s/storage/v1/object/%s/%s' \
    "${SUPABASE_URL%/}" \
    "$(urlencode "$SUPABASE_BACKUP_BUCKET")" \
    "$object"
}

supabase_headers=(
  -H "Authorization: Bearer ${SUPABASE_SECRET_KEY}"
  -H "apikey: ${SUPABASE_SECRET_KEY}"
)

run_backup_cycle() {
  local timestamp object namespace object_query namespace_query digest snapshot restore_response verify_response
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  object="${SUPABASE_BACKUP_PREFIX%/}/${timestamp}-$(openssl rand -hex 8).enc"
  namespace="${BACKUP_RESTORE_NAMESPACE:-phase6-${timestamp}-$(openssl rand -hex 4)}"

  curl --fail --silent --show-error --location \
    --proto '=https' --tlsv1.2 \
    "$BACKUP_SOURCE_URL" > "$workdir/source.json"
  jq -e . "$workdir/source.json" >/dev/null

  openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
    -in "$workdir/source.json" \
    -out "$workdir/backup.enc" \
    -pass env:BACKUP_ENCRYPTION_KEY
  digest="$(sha256sum "$workdir/backup.enc" | awk '{print $1}')"

  curl --fail --silent --show-error \
    --proto '=https' --tlsv1.2 \
    "${supabase_headers[@]}" \
    -H 'Content-Type: application/octet-stream' \
    -H 'x-upsert: false' \
    --data-binary @"$workdir/backup.enc" \
    "$(supabase_storage_url "$object")" >/dev/null

  jq -n \
    --arg object "$object" \
    --arg digest "$digest" \
    --arg namespace "$namespace" \
    --arg createdAt "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{schemaVersion:"1.0.0", object:$object, digest:$digest, restoreNamespace:$namespace, createdAt:$createdAt}' \
    > "$workdir/manifest.json"

  curl --fail --silent --show-error \
    --proto '=https' --tlsv1.2 \
    "${supabase_headers[@]}" \
    -H 'Content-Type: application/json' \
    -H 'x-upsert: false' \
    --data-binary @"$workdir/manifest.json" \
    "$(supabase_storage_url "${object}.manifest.json")" >/dev/null

  curl --fail --silent --show-error --location \
    --proto '=https' --tlsv1.2 \
    "${supabase_headers[@]}" \
    "$(supabase_storage_url "$object")" > "$workdir/download.enc"
  [[ "$(sha256sum "$workdir/download.enc" | awk '{print $1}')" == "$digest" ]] || {
    echo "Downloaded backup digest mismatch" >&2
    exit 1
  }

  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
    -in "$workdir/download.enc" \
    -out "$workdir/restored.json" \
    -pass env:BACKUP_ENCRYPTION_KEY
  snapshot="$(jq -c 'if type == "array" then . else [.] end' "$workdir/restored.json")"

  restore_response="$(
    jq -cn --arg namespace "$namespace" --argjson snapshot "$snapshot" \
      '{namespace: $namespace, snapshot: $snapshot[0]}' \
    | curl --fail --silent --show-error \
        --proto '=https' --tlsv1.2 \
        -H 'Content-Type: application/json' \
        --data-binary @- \
        "$BACKUP_RESTORE_URL"
  )"
  jq -e '.isolated == true' <<<"$restore_response" >/dev/null || {
    echo "Restore endpoint did not confirm isolated restore" >&2
    exit 1
  }

  object_query="$(urlencode "$object")"
  namespace_query="$(urlencode "$namespace")"
  verify_response="$(curl --fail --silent --show-error --location \
    --proto '=https' --tlsv1.2 \
    "${BACKUP_VERIFY_URL}?object=$object_query&namespace=$namespace_query")"
  jq -e --arg digest "$digest" '.digest == $digest' <<<"$verify_response" >/dev/null || {
    echo "Restore verification digest mismatch" >&2
    exit 1
  }

  jq -n --arg object "$object" --arg namespace "$namespace" --arg digest "$digest" \
    '{status:"verified", object:$object, namespace:$namespace, digest:$digest}'
}

case "${1:-}" in
  run) run_backup_cycle ;;
  *) echo "usage: external-supabase-restore.sh run" >&2; exit 2 ;;
esac
