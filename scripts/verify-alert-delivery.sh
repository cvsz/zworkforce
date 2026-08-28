#!/usr/bin/env bash
set -Eeuo pipefail
: "${ALERT_TEST_URL:?ALERT_TEST_URL is required}"
: "${ALERT_DELIVERY_STATUS_URL:?ALERT_DELIVERY_STATUS_URL is required}"
command -v curl >/dev/null
command -v jq >/dev/null
[[ "$ALERT_TEST_URL" == https://* ]] || { echo "ALERT_TEST_URL must use HTTPS" >&2; exit 2; }
[[ "$ALERT_DELIVERY_STATUS_URL" == https://* ]] || { echo "ALERT_DELIVERY_STATUS_URL must use HTTPS" >&2; exit 2; }
AUTH=()
[[ -n "${STAGING_BEARER_TOKEN:-}" ]] && AUTH=(-H "Authorization: Bearer ${STAGING_BEARER_TOKEN}")
ID="phase6-$(date -u +%Y%m%dT%H%M%SZ)-${RANDOM}"
curl --fail --silent --show-error --max-time 30 "${AUTH[@]}" -H 'Content-Type: application/json' -d "{\"testId\":\"$ID\",\"severity\":\"warning\",\"message\":\"Phase 6 alert delivery verification\"}" "$ALERT_TEST_URL" >/dev/null
for _ in $(seq 1 12); do
  BODY="$(curl --fail --silent --show-error --max-time 20 "${AUTH[@]}" "$ALERT_DELIVERY_STATUS_URL?testId=$ID")"
  jq -e '(.delivered == true) or (.status == "delivered")' <<<"$BODY" >/dev/null && { echo "alert delivery verified: $ID"; exit 0; }
  sleep 5
done
echo "alert delivery not confirmed: $ID" >&2
exit 1
