#!/usr/bin/env bash
set -Eeuo pipefail
: "${AI_UPLOAD_URL:?AI_UPLOAD_URL is required}"
[[ "$AI_UPLOAD_URL" == https://* ]] || { echo "AI_UPLOAD_URL must use HTTPS" >&2; exit 2; }
FILE="$(mktemp)"
trap 'rm -f "$FILE"' EXIT
printf 'phase6 upload verification %s\n' "$(date -u +%FT%TZ)" > "$FILE"
AUTH=()
[[ -n "${STAGING_BEARER_TOKEN:-}" ]] && AUTH=(-H "Authorization: Bearer ${STAGING_BEARER_TOKEN}")
RESPONSE="$(curl --fail --silent --show-error --max-time 60 "${AUTH[@]}" -F "file=@$FILE;type=text/plain" "$AI_UPLOAD_URL")"
if command -v jq >/dev/null && jq -e . >/dev/null 2>&1 <<<"$RESPONSE"; then
  jq -e '(.id? // .fileId? // .status?) != null' <<<"$RESPONSE" >/dev/null
else
  test -n "$RESPONSE"
fi
echo "AI upload verified"
