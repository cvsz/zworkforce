#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_EXAMPLE="${1:-${ROOT_DIR}/.env.example}"
OUTPUT_FILE="${2:-${ROOT_DIR}/API-KEY.txt}"
TMP_FILE="$(mktemp)"

cleanup() {
  rm -f "$TMP_FILE"
}
trap cleanup EXIT

if [[ ! -f "$ENV_EXAMPLE" ]]; then
  printf 'error: environment template not found: %s\n' "$ENV_EXAMPLE" >&2
  exit 1
fi

umask 077

# Generate names only. Never copy values from .env or any populated secret file.
awk -F= '
  /^[[:space:]]*[A-Z][A-Z0-9_]*(API_KEY|API_TOKEN|MODELS_TOKEN)[[:space:]]*=/ {
    key=$1
    gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
    print key "="
  }
  /^[[:space:]]*CLOUDFLARE_ACCOUNT_ID[[:space:]]*=/ {
    print "CLOUDFLARE_ACCOUNT_ID="
  }
' "$ENV_EXAMPLE" | LC_ALL=C sort -u > "$TMP_FILE"

install -m 600 "$TMP_FILE" "$OUTPUT_FILE"

printf 'Generated %s placeholders in %s\n' \
  "$(wc -l < "$OUTPUT_FILE" | tr -d ' ')" \
  "$OUTPUT_FILE"
