#!/usr/bin/env bash
set -Eeuo pipefail
: "${AI_FAILOVER_URL:?AI_FAILOVER_URL is required}"
[[ "$AI_FAILOVER_URL" == https://* ]] || { echo "AI_FAILOVER_URL must use HTTPS" >&2; exit 2; }
AUTH=()
[[ -n "${STAGING_BEARER_TOKEN:-}" ]] && AUTH=(-H "Authorization: Bearer ${STAGING_BEARER_TOKEN}")
RESPONSE="$(curl --fail --silent --show-error --max-time 60 "${AUTH[@]}" -H 'Content-Type: application/json' -H 'X-Phase6-Force-Primary-Failure: true' -d '{"messages":[{"role":"user","content":"Return exactly: failover-ok"}],"max_tokens":16}' "$AI_FAILOVER_URL")"
grep -qi 'failover-ok' <<<"$RESPONSE"
if command -v jq >/dev/null && jq -e . >/dev/null 2>&1 <<<"$RESPONSE"; then
  jq -e '(.failover == true) or (.providerRole == "secondary") or (.metadata.failover == true)' <<<"$RESPONSE" >/dev/null
fi
echo "AI failover verified"
