#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/cloudflare/lib/env-scope.sh
source "$SCRIPT_DIR/lib/env-scope.sh"
cf_load_cloudflare_env_scope
cd "$PROJECT_ROOT"

API_BASE="${CLOUDFLARE_API_BASE:-https://api.cloudflare.com/client/v4}"
BASE_ENV_FILE="${CLOUDFLARE_ENV_FILE:-${ENV_FILE:-$PROJECT_ROOT/.env}}"
SCOPED_ENV_FILE="${CLOUDFLARE_TOKEN_ENV_FILE:-${TOKEN_FILE:-$PROJECT_ROOT/.env.cloudflare}}"

log(){ cf_env_log "$*"; }
die(){ cf_env_die "$*"; }

[[ "${CONFIRM_BOOTSTRAP_ROLL:-}" == "YES" ]] || die "CONFIRM_BOOTSTRAP_ROLL=YES is required"
cf_require_env CLOUDFLARE_ACCOUNT_ID CLOUDFLARE_BOOTSTRAP_TOKEN || exit 1
command -v curl >/dev/null 2>&1 || die "curl is required"
command -v jq >/dev/null 2>&1 || die "jq is required"

for env_file in "$BASE_ENV_FILE" "$SCOPED_ENV_FILE"; do
  [[ -f "$env_file" ]] || die "required env file not found: $env_file"
  [[ -r "$env_file" && -w "$env_file" ]] || die "env file must be readable and writable: $env_file"
done

work_dir="$(mktemp -d "${TMPDIR:-/tmp}/z-platform-bootstrap-roll.XXXXXX")"
verify_file="$work_dir/verify.json"
roll_file="$work_dir/roll.json"
new_value_file="$work_dir/new-value"
base_next="$work_dir/base.env.next"
token_next="$work_dir/token.env.next"
rolled=false

cleanup(){
  if [[ "$rolled" == "true" && ( ! -s "$base_next" || ! -s "$token_next" ) ]]; then
    log "ERROR: rolled token recovery material retained at $work_dir"
    return
  fi
  rm -rf -- "$work_dir"
}
trap cleanup EXIT

request_to_file(){
  local method="$1" endpoint="$2" output="$3" token_file="${4:-}" http_code
  if [[ -n "$token_file" ]]; then
    http_code="$(curl -sS -o "$output" -w '%{http_code}' -X "$method" \
      -H "Authorization: Bearer $(<"$token_file")" \
      -H 'Content-Type: application/json' --data '{}' "${API_BASE}${endpoint}")"
  else
    http_code="$(curl -sS -o "$output" -w '%{http_code}' -X "$method" \
      -H "Authorization: Bearer ${CLOUDFLARE_BOOTSTRAP_TOKEN}" \
      -H 'Content-Type: application/json' --data '{}' "${API_BASE}${endpoint}")"
  fi
  [[ "$http_code" =~ ^2[0-9][0-9]$ ]] || die "Cloudflare API request failed: method=$method endpoint=$endpoint http=$http_code"
  jq -e '.success == true' "$output" >/dev/null || die "Cloudflare API returned success=false"
}

request_to_file GET "/accounts/${CLOUDFLARE_ACCOUNT_ID}/tokens/verify" "$verify_file"
token_id="$(jq -r '.result.id // empty' "$verify_file")"
[[ "$token_id" =~ ^[0-9a-f]{32}$ ]] || die "verified bootstrap token did not return a valid token ID"
[[ "$(jq -r '.result.status // empty' "$verify_file")" == "active" ]] || die "bootstrap token is not active"

log "rolling verified account-owned bootstrap token"
request_to_file PUT "/accounts/${CLOUDFLARE_ACCOUNT_ID}/tokens/${token_id}/value" "$roll_file"
jq -er '.result | select(type == "string" and length >= 20)' "$roll_file" > "$new_value_file" \
  || die "roll response did not contain a token value"
rolled=true

request_to_file GET "/accounts/${CLOUDFLARE_ACCOUNT_ID}/tokens/verify" "$verify_file" "$new_value_file"
[[ "$(jq -r '.result.status // empty' "$verify_file")" == "active" ]] || die "rolled bootstrap token failed verification"

rewrite_env(){
  local source_file="$1" destination_file="$2"
  awk '
    NR == FNR { replacement = $0; next }
    /^(CLOUDFLARE_BOOTSTRAP_TOKEN|CLOUDFLARE_API_TOKEN)=/ {
      key = $0
      sub(/=.*/, "", key)
      print key "=\"" replacement "\""
      seen[key] = 1
      next
    }
    { print }
    END {
      if (!("CLOUDFLARE_BOOTSTRAP_TOKEN" in seen)) print "CLOUDFLARE_BOOTSTRAP_TOKEN=\"" replacement "\""
      if (!("CLOUDFLARE_API_TOKEN" in seen)) print "CLOUDFLARE_API_TOKEN=\"" replacement "\""
    }
  ' "$new_value_file" "$source_file" > "$destination_file"
  chmod 600 "$destination_file"
}

rewrite_env "$BASE_ENV_FILE" "$base_next"
rewrite_env "$SCOPED_ENV_FILE" "$token_next"
mv -f -- "$base_next" "$BASE_ENV_FILE"
mv -f -- "$token_next" "$SCOPED_ENV_FILE"
rolled=false

log "bootstrap token rolled, verified, and atomically updated in local env files"
