#!/usr/bin/env bash

# discover-permission-groups.sh
# Retrieves Cloudflare API token or IAM permission groups for the configured account and caches the result.
#
# Usage:
#   discover-permission-groups.sh [--refresh] [--json] [--iam]
#
#   --refresh   Skip cache and fetch fresh data from Cloudflare API.
#   --json      Output the raw JSON response to stdout.
#   --iam       Fetch IAM groups instead of API token permission groups.
#
# Environment variables required:
#   CLOUDFLARE_ACCOUNT_ID       Cloudflare account identifier.
#   CLOUDFLARE_BOOTSTRAP_TOKEN  API token with appropriate permissions.
#
# The script writes a cached file to:
#   - .cache/cloudflare-permissions/account-token-permission-groups.<account_id>.json (default)
#   - .cache/cloudflare-permissions/groups.json (with --iam flag)

set -euo pipefail

# Parse flags
REFRESH=false
JSON_OUTPUT=false
IAM_MODE=false

while (( "$#" )); do
  case "$1" in
    --refresh) REFRESH=true ; shift ;;
    --json)    JSON_OUTPUT=true ; shift ;;
    --iam)     IAM_MODE=true ; shift ;;
    -h|--help) echo "Usage: $0 [--refresh] [--json] [--iam]" ; exit 0 ;;
    *) echo "Unknown option: $1" ; exit 1 ;;
  esac
done

# Verify required env vars
: "${CLOUDFLARE_ACCOUNT_ID:?Missing CLOUDFLARE_ACCOUNT_ID}"
: "${CLOUDFLARE_BOOTSTRAP_TOKEN:?Missing CLOUDFLARE_BOOTSTRAP_TOKEN}"

CACHE_DIR=".cache/cloudflare-permissions"
if $IAM_MODE; then
  CACHE_FILE="$CACHE_DIR/groups.json"
  ENDPOINT="/accounts/${CLOUDFLARE_ACCOUNT_ID}/iam/groups"
else
  CACHE_FILE="$CACHE_DIR/account-token-permission-groups.${CLOUDFLARE_ACCOUNT_ID}.json"
  ENDPOINT="/accounts/${CLOUDFLARE_ACCOUNT_ID}/tokens/permission_groups"
fi

mkdir -p "$CACHE_DIR"

# Function to fetch from API
fetch_groups() {
  local api_base="${CLOUDFLARE_API_BASE:-https://api.cloudflare.com/client/v4}"
  local url="${api_base}${ENDPOINT}"
  local response
  response=$(curl -sSf -X GET "$url" \
    -H "Authorization: Bearer ${CLOUDFLARE_BOOTSTRAP_TOKEN}" \
    -H "Content-Type: application/json")
  # Save cache
  echo "$response" > "$CACHE_FILE"
  chmod 600 "$CACHE_FILE"
  echo "$response"
}

# Main logic
if $REFRESH || [ ! -f "$CACHE_FILE" ]; then
  RESULT=$(fetch_groups)
else
  RESULT=$(cat "$CACHE_FILE")
fi

if $JSON_OUTPUT; then
  echo "$RESULT"
else
  # Pretty‑print a summary: list group name -> id
  if $IAM_MODE; then
    echo "IAM groups for account ${CLOUDFLARE_ACCOUNT_ID}:"
  else
    echo "API Token Permission groups for account ${CLOUDFLARE_ACCOUNT_ID}:"
  fi
  echo "$RESULT" | jq -r '.result[] | "- \(.name): \(.id)"'
fi
