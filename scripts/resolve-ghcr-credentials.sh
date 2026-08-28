#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf 'GHCR credential resolution failed: %s\n' "$1" >&2
  exit 1
}

pair_state() {
  local username=${1:-}
  local token=${2:-}
  if [[ -n "$username" && -n "$token" ]]; then
    printf 'complete'
  elif [[ -z "$username" && -z "$token" ]]; then
    printf 'empty'
  else
    printf 'partial'
  fi
}

legacy_state=$(pair_state "${GHCR_USERNAME:-}" "${GHCR_PULL_TOKEN:-}")
oauth_state=$(pair_state "${GHCR_OAUTH_ID:-}" "${GHCR_OAUTH_TOKEN:-}")

[[ "$legacy_state" != partial ]] || fail 'GHCR_USERNAME and GHCR_PULL_TOKEN must be provided together'
[[ "$oauth_state" != partial ]] || fail 'GHCR_OAUTH_ID and GHCR_OAUTH_TOKEN must be provided together'

if [[ "$legacy_state" == complete ]]; then
  effective_username=$GHCR_USERNAME
  effective_token=$GHCR_PULL_TOKEN
  source_name=legacy
elif [[ "$oauth_state" == complete ]]; then
  effective_username=$GHCR_OAUTH_ID
  effective_token=$GHCR_OAUTH_TOKEN
  source_name=oauth
else
  fail 'provide either the legacy or OAuth credential pair'
fi

[[ "$effective_username" != *$'\n'* && "$effective_username" != *$'\r'* ]] || fail 'username contains a line break'
[[ "$effective_token" != *$'\n'* && "$effective_token" != *$'\r'* ]] || fail 'token contains a line break'
[[ -n "${GITHUB_ENV:-}" ]] || fail 'GITHUB_ENV is required'

{
  printf 'GHCR_EFFECTIVE_USERNAME=%s\n' "$effective_username"
  printf 'GHCR_EFFECTIVE_TOKEN=%s\n' "$effective_token"
  printf 'GHCR_CREDENTIAL_SOURCE=%s\n' "$source_name"
} >> "$GITHUB_ENV"
