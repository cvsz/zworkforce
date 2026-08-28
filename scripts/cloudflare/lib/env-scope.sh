#!/usr/bin/env bash
# Shared Cloudflare environment loader for token verification and rotation.
# Canonical behavior:
#   1. Pre-existing shell exports have highest priority for protected bootstrap keys.
#   2. .env is the bootstrap/base file.
#   3. .env.cloudflare is the generated scoped-token file.
#   4. Generated token file may provide scoped tokens, but should not override bootstrap identity.

set -Eeuo pipefail
IFS=$'\n\t'

cf_env_log(){ printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
cf_env_warn(){ cf_env_log "WARN: $*" >&2; }
cf_env_die(){ cf_env_log "ERROR: $*" >&2; exit 1; }

cf_find_root(){
  local root="${PROJECT_ROOT:-}"
  if [[ -z "$root" ]]; then
    root="$PWD"
    while [[ "$root" != "/" ]]; do
      if [[ -d "$root/.git" || -f "$root/.env.example" || -f "$root/Makefile" ]]; then
        break
      fi
      root="$(dirname "$root")"
    done
  fi
  [[ "$root" != "/" ]] || root="$PWD"
  printf '%s' "$root"
}

cf_mask(){
  local value="${1:-}"
  local len="${#value}"
  if [[ "$len" -le 8 ]]; then
    printf '<missing-or-too-short>'
  else
    printf '%s...%s len=%s' "${value:0:4}" "${value: -4}" "$len"
  fi
}

cf_file_has_key(){
  local file="$1" key="$2"
  [[ -f "$file" ]] || return 1
  grep -qE "^${key}=" "$file"
}

cf_source_env_file(){
  local file="$1"
  [[ -f "$file" ]] || return 0
  set -a
  # shellcheck disable=SC1090
  source "$file"
  set +a
}

cf_capture_protected_values(){
  local prefix="$1" key
  for key in CLOUDFLARE_ACCOUNT_ID CLOUDFLARE_ZONE_ID CLOUDFLARE_BOOTSTRAP_TOKEN CLOUDFLARE_API_BASE; do
    printf -v "${prefix}_${key}" '%s' "${!key-}"
    if [[ -n "${!key+x}" ]]; then
      printf -v "${prefix}_${key}_SET" '%s' "1"
    else
      printf -v "${prefix}_${key}_SET" '%s' "0"
    fi
  done
}

cf_restore_protected_key(){
  local key="$1" env_set env_val base_set base_val token_set token_val
  env_set="CF_ENV_BEFORE_${key}_SET"
  env_val="CF_ENV_BEFORE_${key}"
  base_set="CF_ENV_BASE_${key}_SET"
  base_val="CF_ENV_BASE_${key}"
  token_set="CF_ENV_TOKEN_${key}_SET"
  token_val="CF_ENV_TOKEN_${key}"

  if [[ "${!env_set:-0}" == "1" && -n "${!env_val:-}" ]]; then
    export "$key=${!env_val}"
  elif [[ "${!base_set:-0}" == "1" && -n "${!base_val:-}" ]]; then
    export "$key=${!base_val}"
  elif [[ "${!token_set:-0}" == "1" && -n "${!token_val:-}" ]]; then
    export "$key=${!token_val}"
  else
    unset "$key"
  fi
}

cf_load_cloudflare_env_scope(){
  local root env_file token_env_file key
  root="$(cf_find_root)"
  cd "$root"

  env_file="${CLOUDFLARE_ENV_FILE:-${ENV_FILE:-$root/.env}}"
  token_env_file="${CLOUDFLARE_TOKEN_ENV_FILE:-${TOKEN_ENV_FILE:-$root/.env.cloudflare}}"

  cf_capture_protected_values CF_ENV_BEFORE
  cf_source_env_file "$env_file"
  cf_capture_protected_values CF_ENV_BASE
  cf_source_env_file "$token_env_file"
  cf_capture_protected_values CF_ENV_TOKEN

  if [[ "${CLOUDFLARE_ENV_PROTECT_BOOTSTRAP:-true}" == "true" ]]; then
    for key in CLOUDFLARE_ACCOUNT_ID CLOUDFLARE_ZONE_ID CLOUDFLARE_BOOTSTRAP_TOKEN CLOUDFLARE_API_BASE; do
      cf_restore_protected_key "$key"
    done
  fi

  : "${CLOUDFLARE_AI_GATEWAY_SLUG:=zeaz}"
  export CLOUDFLARE_AI_GATEWAY_SLUG
  export PROJECT_ROOT="$root"
}

cf_print_env_sources(){
  local env_file token_env_file key sources
  env_file="${CLOUDFLARE_ENV_FILE:-${ENV_FILE:-${PROJECT_ROOT:-$(cf_find_root)}/.env}}"
  token_env_file="${CLOUDFLARE_TOKEN_ENV_FILE:-${TOKEN_ENV_FILE:-${PROJECT_ROOT:-$(cf_find_root)}/.env.cloudflare}}"

  cf_env_log "Cloudflare env source check"
  for key in "$@"; do
    sources=()
    [[ -n "${!key+x}" ]] && sources+=(shell-or-loaded)
    cf_file_has_key "$env_file" "$key" && sources+=(.env)
    cf_file_has_key "$token_env_file" "$key" && sources+=(.env.cloudflare)
    printf '%s sources: %s\n' "$key" "${sources[*]:-<none>}"
  done
}

cf_require_env(){
  local missing=0 key
  for key in "$@"; do
    if [[ -z "${!key:-}" ]]; then
      cf_env_log "ERROR: ${key} is missing" >&2
      missing=$((missing + 1))
    fi
  done
  [[ "$missing" -eq 0 ]]
}
