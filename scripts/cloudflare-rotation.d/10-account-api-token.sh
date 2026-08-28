#!/usr/bin/env bash
set -Eeuo pipefail

# Real Cloudflare account-token rotation. This hook intentionally requires a
# separate bootstrap token. Rolling the runtime token with itself would leave
# the next scheduled run without an independent recovery credential.

ENV_FILE="${1:?rotation environment file is required}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BOOTSTRAP_ENV_FILE="${ROTATION_BOOTSTRAP_ENV_FILE:-$HOME/.config/zworkforce/cloudflare-rotation.env}"
OUT_DIR="${ROTATION_OUT_DIR:-$ROOT/output/cloudflare-rotation}"
API_ROOT="${CLOUDFLARE_API_ROOT:-https://api.cloudflare.com/client/v4}"

fail() {
  printf 'cloudflare account-token rotation: %s\n' "$1" >&2
  exit "${2:-1}"
}

require_secret_file() {
  local path="$1" label="$2" mode
  [[ -f "$path" && ! -L "$path" ]] || fail "$label must be a regular file: $path"
  mode="$(stat -c '%a' "$path")"
  (( (8#$mode & 8#077) == 0 )) || fail "$label must be mode 600 or stricter: $path"
}

read_env_value() {
  local key="$1" file="$2"
  awk -F= -v wanted="$key" '
    /^[[:space:]]*#/ { next }
    {
      name=$1
      sub(/^[[:space:]]*(export[[:space:]]+)?/, "", name)
      gsub(/[[:space:]]+$/, "", name)
      if (name != wanted) next
      value=substr($0, index($0, "=") + 1)
      sub(/^[[:space:]]+/, "", value)
      sub(/[[:space:]]+$/, "", value)
      if (value ~ /^".*"$/ || value ~ /^'"'"'.*'"'"'$/) value=substr(value, 2, length(value) - 2)
      print value
      exit
    }
  ' "$file"
}

require_secret_file "$ENV_FILE" "Cloudflare environment"
require_secret_file "$BOOTSTRAP_ENV_FILE" "rotation bootstrap environment"

runtime_token="$(read_env_value CLOUDFLARE_API_TOKEN "$ENV_FILE")"
account_id="$(read_env_value CLOUDFLARE_ACCOUNT_ID "$ENV_FILE")"
tunnel_id="$(read_env_value CLOUDFLARE_TUNNEL_ID "$ENV_FILE")"
bootstrap_token="$(read_env_value CLOUDFLARE_ROTATION_BOOTSTRAP_TOKEN "$BOOTSTRAP_ENV_FILE")"

[[ -n "$runtime_token" ]] || fail "CLOUDFLARE_API_TOKEN is missing"
[[ -n "$account_id" ]] || fail "CLOUDFLARE_ACCOUNT_ID is missing"
[[ -n "$tunnel_id" ]] || fail "CLOUDFLARE_TUNNEL_ID is missing"
[[ -n "$bootstrap_token" ]] || fail "CLOUDFLARE_ROTATION_BOOTSTRAP_TOKEN is missing"
[[ "$runtime_token" != "$bootstrap_token" ]] || {
  fail "bootstrap and runtime tokens must be different; refusing self-rotation"
}

api_get() {
  local token="$1" path="$2" response
  response="$(curl --silent --show-error --fail-with-body --max-time 30 \
    -H "Authorization: Bearer $token" \
    "$API_ROOT$path")" || fail "Cloudflare API GET failed: $path"
  printf '%s' "$response"
}

api_roll() {
  local token="$1" path="$2" response
  response="$(curl --silent --show-error --fail-with-body --max-time 30 \
    -X PUT \
    -H "Authorization: Bearer $token" \
    -H 'Content-Type: application/json' \
    -d '{}' \
    "$API_ROOT$path")" || fail "Cloudflare API token roll failed"
  printf '%s' "$response"
}

runtime_verify="$(api_get "$runtime_token" "/accounts/$account_id/tokens/verify")"
runtime_id="$(printf '%s' "$runtime_verify" | jq -er '.result.id')" || fail "current runtime token verification failed"
[[ "$(printf '%s' "$runtime_verify" | jq -r '.success // false')" == true ]] || fail "current runtime token is not active"

bootstrap_verify="$(api_get "$bootstrap_token" "/accounts/$account_id/tokens/verify")"
bootstrap_id="$(printf '%s' "$bootstrap_verify" | jq -er '.result.id')" || fail "bootstrap token verification failed"
[[ "$runtime_id" != "$bootstrap_id" ]] || fail "bootstrap and runtime token IDs must be different"

rolled="$(api_roll "$bootstrap_token" "/accounts/$account_id/tokens/$runtime_id/value")"
[[ "$(printf '%s' "$rolled" | jq -r '.success // false')" == true ]] || fail "Cloudflare did not roll the runtime token"
new_token="$(printf '%s' "$rolled" | jq -er '.result')" || fail "Cloudflare returned no replacement token"

new_verify="$(api_get "$new_token" "/accounts/$account_id/tokens/verify")"
[[ "$(printf '%s' "$new_verify" | jq -r '.success // false')" == true ]] || fail "replacement token verification failed"
[[ "$(printf '%s' "$new_verify" | jq -r '.result.id')" == "$runtime_id" ]] || fail "replacement token ID changed unexpectedly"
[[ "$(printf '%s' "$new_verify" | jq -r '.result.status')" == active ]] || fail "replacement token is not active"

tunnel_status="$(api_get "$new_token" "/accounts/$account_id/cfd_tunnel/$tunnel_id")"
[[ "$(printf '%s' "$tunnel_status" | jq -r '.success // false')" == true ]] || fail "replacement token cannot read the configured tunnel"

env_dir="$(dirname "$ENV_FILE")"
env_tmp="$(mktemp "$env_dir/.env.cloudflare.rotation.XXXXXX")"
cleanup() {
  if [[ -n "${env_tmp:-}" && -e "$env_tmp" ]]; then
    rm -f -- "$env_tmp"
  fi
}
trap cleanup EXIT

awk -v replacement="$new_token" '
  BEGIN { count=0 }
  /^[[:space:]]*(export[[:space:]]+)?CLOUDFLARE_API_TOKEN[[:space:]]*=/ {
    print "CLOUDFLARE_API_TOKEN=" replacement
    count++
    next
  }
  { print }
  END { if (count != 1) exit 17 }
' "$ENV_FILE" > "$env_tmp" || fail "environment file must contain exactly one CLOUDFLARE_API_TOKEN assignment"
chmod 600 "$env_tmp"
mv -f "$env_tmp" "$ENV_FILE"
env_tmp=""

umask 077
mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR"
evidence="$OUT_DIR/account-api-token-$(date -u +%Y%m%dT%H%M%SZ).json"
jq -n \
  --arg token_id "$runtime_id" \
  --arg tunnel_id "$tunnel_id" \
  --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '{schema: 1, credential: "account-api-token", token_id: $token_id,
    tunnel_id: $tunnel_id, verified: true, timestamp: $timestamp}' > "$evidence"
chmod 600 "$evidence"
printf 'account_api_token_rotated=true\n'
