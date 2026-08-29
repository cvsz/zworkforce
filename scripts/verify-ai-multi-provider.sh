#!/usr/bin/env bash
set -Eeuo pipefail
: "${AI_PROVIDER_ENDPOINTS:?AI_PROVIDER_ENDPOINTS is required as comma-separated HTTPS URLs}"
IFS=',' read -r -a ENDPOINTS <<<"$AI_PROVIDER_ENDPOINTS"
((${#ENDPOINTS[@]} >= 2)) || { echo "at least two provider endpoints are required" >&2; exit 2; }
AUTH=()
[[ -n "${STAGING_BEARER_TOKEN:-}" ]] && AUTH=(-H "Authorization: Bearer ${STAGING_BEARER_TOKEN}")
for endpoint in "${ENDPOINTS[@]}"; do
  endpoint="${endpoint//[[:space:]]/}"
  [[ "$endpoint" == https://* ]] || { echo "provider endpoint must use HTTPS: $endpoint" >&2; exit 2; }
  curl --fail --silent --show-error --max-time 45 "${AUTH[@]}" -H 'Content-Type: application/json' -d '{"messages":[{"role":"user","content":"Return exactly: phase6-ok"}],"max_tokens":16}' "$endpoint" | grep -qi 'phase6-ok'
done
echo "multi-provider verification passed for ${#ENDPOINTS[@]} providers"
