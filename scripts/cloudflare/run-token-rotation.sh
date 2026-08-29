#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/cloudflare/lib/env-scope.sh
source "$SCRIPT_DIR/lib/env-scope.sh"
cf_load_cloudflare_env_scope
cd "$PROJECT_ROOT"

API_BASE="${CLOUDFLARE_API_BASE:-https://api.cloudflare.com/client/v4}"
OFFLINE=false

log(){ cf_env_log "$*"; }
warn(){ cf_env_warn "$*"; }
die(){ cf_env_die "$*"; }

contains_arg(){
  local wanted="$1"
  shift
  local arg
  for arg in "$@"; do
    [[ "$arg" == "$wanted" ]] && return 0
  done
  return 1
}

value_after_arg(){
  local wanted="$1"
  shift
  local prev=""
  local arg
  for arg in "$@"; do
    if [[ "$prev" == "$wanted" ]]; then
      printf '%s' "$arg"
      return 0
    fi
    prev="$arg"
  done
  return 1
}

for arg in "$@"; do
  [[ "$arg" == "--offline" ]] && OFFLINE=true
done

is_cleanup_only(){
  ! contains_arg --regenerate "$@"
}

request_verify(){
  local label="$1" endpoint="$2" body_file err_file http_code curl_rc body err ok errors
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
      errors="$(printf '%s' "$body" | jq -c '.errors // []')"
    else
      errors="$body"
    fi
    warn "$label verify failed: http=${http_code} errors=${errors}"
    return 22
  fi

  ok="$(printf '%s' "$body" | jq -r '.success // false' 2>/dev/null || printf 'false')"
  if [[ "$ok" != "true" ]]; then
    errors="$(printf '%s' "$body" | jq -c '.errors // []' 2>/dev/null || printf '[]')"
    warn "$label verify success=false errors=${errors}"
    return 23
  fi

  log "verified CLOUDFLARE_BOOTSTRAP_TOKEN as $label"
  return 0
}

verify_bootstrap_token(){
  command -v curl >/dev/null 2>&1 || die "curl is required"
  command -v jq >/dev/null 2>&1 || die "jq is required"

  if [[ -n "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
    if request_verify "account-token" "/accounts/${CLOUDFLARE_ACCOUNT_ID}/tokens/verify"; then
      return 0
    fi
  else
    warn "CLOUDFLARE_ACCOUNT_ID is missing; skipping account-token verify endpoint"
  fi

  if request_verify "user-token" "/user/tokens/verify"; then
    return 0
  fi

  return 1
}

if is_cleanup_only "$@"; then
  if $OFFLINE; then
    cf_require_env CLOUDFLARE_ACCOUNT_ID || exit 1
  elif [[ -z "${CLOUDFLARE_ACCOUNT_ID:-}" || -z "${CLOUDFLARE_BOOTSTRAP_TOKEN:-}" ]]; then
    warn "token-clean skipped: CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_BOOTSTRAP_TOKEN is missing"
    warn "run make token-verify after filling .env, then rerun make token-clean"
    exit 0
  elif ! verify_bootstrap_token; then
    warn "token-clean skipped: bootstrap token verification failed"
    warn "run make token-verify for a masked diagnostic"
    exit 0
  fi
else
  if $OFFLINE; then
    cf_require_env CLOUDFLARE_ACCOUNT_ID || exit 1
    log "offline mode: skipping bootstrap token verification"
  else
    cf_require_env CLOUDFLARE_ACCOUNT_ID CLOUDFLARE_BOOTSTRAP_TOKEN || exit 1
    verify_bootstrap_token || die "CLOUDFLARE_BOOTSTRAP_TOKEN verification failed. Run make token-verify."
  fi
fi

if contains_arg --regenerate "$@"; then
  types="$(value_after_arg --types "$@" || true)"
  [[ -n "$types" ]] || die "--regenerate requires --types"
  if [[ "$types" == "all" || ",$types," == *",dns,"* || ",$types," == *",waf,"* ]]; then
    [[ -n "${CLOUDFLARE_ZONE_ID:-}" ]] || die "CLOUDFLARE_ZONE_ID is missing. DNS/WAF token creation needs the real Cloudflare zone ID."
  fi
fi

exec bash scripts/cloudflare/clean-and-regenerate-tokens.sh "$@"
