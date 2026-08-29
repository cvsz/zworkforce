#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/cloudflare/lib/env-scope.sh
source "$SCRIPT_DIR/lib/env-scope.sh"
cf_load_cloudflare_env_scope
cd "$PROJECT_ROOT"

[[ "${CONFIRM_LEGACY_SCRUB:-}" == "YES" ]] || cf_env_die "CONFIRM_LEGACY_SCRUB=YES is required"

base_env_file="${CLOUDFLARE_ENV_FILE:-${ENV_FILE:-$PROJECT_ROOT/.env}}"
scoped_env_file="${CLOUDFLARE_TOKEN_ENV_FILE:-${TOKEN_FILE:-$PROJECT_ROOT/.env.cloudflare}}"
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/z-platform-legacy-scrub.XXXXXX")"
trap 'rm -rf -- "$work_dir"' EXIT

scrub_file(){
  local source_file="$1" destination_file="$2"
  [[ -f "$source_file" ]] || cf_env_die "required env file not found: $source_file"
  awk -F= '
    $1 == "CLOUDFLARE_GLOBAL_TOKEN" { next }
    $1 == "ACCESS_KEY_ID" { next }
    $1 == "ACCESS_SECRET_KEY" { next }
    $1 == "S3_API_ENDPOINT" { next }
    { print }
  ' "$source_file" > "$destination_file"
  chmod 600 "$destination_file"
}

scrub_file "$base_env_file" "$work_dir/base.env.next"
scrub_file "$scoped_env_file" "$work_dir/scoped.env.next"
mv -f -- "$work_dir/base.env.next" "$base_env_file"
mv -f -- "$work_dir/scoped.env.next" "$scoped_env_file"

cf_env_log "deprecated global-key and R2/S3 credential entries removed from local env files"
