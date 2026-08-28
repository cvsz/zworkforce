#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/cloudflare/lib/env-scope.sh
source "$SCRIPT_DIR/lib/env-scope.sh"
cf_load_cloudflare_env_scope
cd "$PROJECT_ROOT"

API_BASE="${CLOUDFLARE_API_BASE:-https://api.cloudflare.com/client/v4}"

log(){ cf_env_log "$*"; }
warn(){ cf_env_warn "$*"; }
die(){ cf_env_die "$*"; }

request_verify(){
  local label="$1" endpoint="$2" body_file err_file http_code curl_rc body err success
  body_file="$(mktemp)"
  err_file="$(mktemp)"

  set +e
  http_code="$(curl -sS -o "$body_file" -w '%{http_code}' \
    -H "Authorization: Bearer ${CLOUDFLARE_BOOTSTRAP_TOKEN}" \
    "${API_BASE}${endpoint}" 2>"$err_file")"
  curl_rc=$?
  set -e

  body="$(cat "$body_file")"
  err="$(cat "$err_file")"
  rm -f "$body_file" "$err_file"

  if [[ "$curl_rc" -ne 0 ]]; then
    warn "$label verify curl failed: rc=${curl_rc} http=${http_code:-000} stderr=${err:-<empty>}"
    return 20
  fi

  if [[ -z "$body" ]]; then
    warn "$label verify returned an empty body: http=${http_code:-000}; endpoint=${endpoint}"
    return 21
  fi

  if [[ ! "$http_code" =~ ^2[0-9][0-9]$ ]]; then
    if printf '%s' "$body" | jq -e . >/dev/null 2>&1; then
      printf '%s\n' "$body" | jq -c --arg label "$label" --arg http "$http_code" '{label:$label,http:$http,success:(.success // false),errors:(.errors // []),messages:(.messages // [])}' >&2
    else
      warn "$label verify failed with HTTP ${http_code}: ${body}"
    fi
    return 22
  fi

  success="$(printf '%s' "$body" | jq -r '.success // false' 2>/dev/null || printf 'false')"
  if [[ "$success" != "true" ]]; then
    printf '%s\n' "$body" | jq -c --arg label "$label" '{label:$label,success:(.success // false),errors:(.errors // []),messages:(.messages // [])}' >&2
    return 23
  fi

  printf '%s\n' "$body" | jq -c --arg label "$label" '{label:$label,success:(.success // false),result:{id:(.result.id // null),status:(.result.status // null)}}'
  return 0
}

cf_print_env_sources CLOUDFLARE_ACCOUNT_ID CLOUDFLARE_ZONE_ID CLOUDFLARE_BOOTSTRAP_TOKEN
cf_require_env CLOUDFLARE_ACCOUNT_ID CLOUDFLARE_ZONE_ID CLOUDFLARE_BOOTSTRAP_TOKEN || exit 1

printf 'CLOUDFLARE_ACCOUNT_ID: %s\n' "$(cf_mask "$CLOUDFLARE_ACCOUNT_ID")"
printf 'CLOUDFLARE_ZONE_ID: %s\n' "$(cf_mask "$CLOUDFLARE_ZONE_ID")"
printf 'CLOUDFLARE_BOOTSTRAP_TOKEN: %s\n' "$(cf_mask "$CLOUDFLARE_BOOTSTRAP_TOKEN")"

command -v curl >/dev/null 2>&1 || die "curl is required"
command -v jq >/dev/null 2>&1 || die "jq is required"

if request_verify "account-token" "/accounts/${CLOUDFLARE_ACCOUNT_ID}/tokens/verify"; then
  log "CLOUDFLARE_BOOTSTRAP_TOKEN is a valid account token"
  exit 0
fi

if request_verify "user-token" "/user/tokens/verify"; then
  log "CLOUDFLARE_BOOTSTRAP_TOKEN is a valid user token"
  exit 0
fi

die "CLOUDFLARE_BOOTSTRAP_TOKEN could not be verified as an account token or user token"
