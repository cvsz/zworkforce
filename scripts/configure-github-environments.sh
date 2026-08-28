#!/usr/bin/env bash
set -Eeuo pipefail

REPO="${REPO:-cvsz/z-platform}"
GITHUB_API_VERSION="${GITHUB_API_VERSION:-2026-03-10}"
PREVENT_SELF_REVIEW="${PREVENT_SELF_REVIEW:-true}"
STAGING_BRANCH_POLICY="${STAGING_BRANCH_POLICY:-protected}"
STAGING_BRANCH_NAME="${STAGING_BRANCH_NAME:-main}"
PRODUCTION_BRANCH_POLICY="${PRODUCTION_BRANCH_POLICY:-main-only}"
PRODUCTION_BRANCH_NAME="${PRODUCTION_BRANCH_NAME:-main}"

declare -A LOADED_ENV_KEYS=()

usage() {
  cat <<'EOF'
Usage:
  scripts/configure-github-environments.sh \
    [--env-file .env] \
    [--env-file .env.phase6] \
    [--env-file .env.phase6.server] \
    [--staging-reviewer user:LOGIN|team:SLUG] \
    [--staging-reviewer ...] \
    [--production-reviewer user:LOGIN|team:SLUG] \
    [--production-reviewer ...]

Environment variables:
  REPO                     Repository in OWNER/REPO form. Default: cvsz/z-platform
  GITHUB_API_VERSION       GitHub API version header. Default: 2026-03-10
  PREVENT_SELF_REVIEW      true or false. Default: true
  STAGING_BRANCH_POLICY    protected or main-only. Default: protected
  STAGING_BRANCH_NAME      Deployment branch name when using main-only. Default: main
  PRODUCTION_BRANCH_POLICY  protected or main-only. Default: main-only
  PRODUCTION_BRANCH_NAME   Deployment branch name when using main-only. Default: main

Default overlay order:
  .env
  .env.phase6
  .env.phase6.server

Selectors:
  user:LOGIN               Resolve a GitHub user by login and use that user ID.
  team:SLUG                Resolve a GitHub team slug in the repository owner org.
  LOGIN                     Treated as user:LOGIN when loaded from .env overlays.

The script configures environment protection rules and imports populated keys
from the loaded env overlays into GitHub environment variables and secrets.
It never prints secret values.
EOF
}

die() {
  echo "error: $*" >&2
  exit 2
}

require_cmd() {
  command -v "$1" >/dev/null || die "$1 is required"
}

require_gh() {
  require_cmd gh
  gh auth status >/dev/null
}

require_jq() {
  require_cmd jq
}

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

json_bool() {
  case "${1,,}" in
    true|1|yes|on)
      printf '%s' true
      ;;
    false|0|no|off)
      printf '%s' false
      ;;
    *)
      die "expected a boolean value, got: $1"
      ;;
  esac
}

load_env_file() {
  local file="$1"
  [[ -f "$file" ]] || return 0

  local line name value
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    line="$(trim "$line")"
    [[ -z "$line" ]] && continue
    [[ "$line" == \#* ]] && continue
    [[ "$line" == export\ * ]] && line="$(trim "${line#export }")"
    [[ "$line" == *"="* ]] || continue

    name="${line%%=*}"
    value="${line#*=}"
    name="$(trim "$name")"
    value="$(trim "$value")"

    [[ "$name" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue

    case "$value" in
      \"*\")
        value="${value:1:${#value}-2}"
        ;;
      \'*\')
        value="${value:1:${#value}-2}"
        ;;
    esac

    printf -v "$name" '%s' "$value"
    export "$name"
    LOADED_ENV_KEYS["$name"]=1
  done < "$file"
}

load_default_env_files() {
  local file
  for file in .env .env.phase6 .env.phase6.server; do
    load_env_file "$file"
  done
}

normalize_reviewer_selector() {
  local selector="$1"
  [[ -n "$selector" ]] || die "reviewer selector is required"

  if [[ "$selector" == *:* ]]; then
    printf '%s' "$selector"
  else
    printf 'user:%s' "$selector"
  fi
}

resolve_reviewer_id() {
  local selector kind value owner
  selector="$(normalize_reviewer_selector "$1")"
  kind="${selector%%:*}"
  value="${selector#*:}"

  [[ -n "$value" ]] || die "reviewer selector is missing a value: $selector"

  case "$kind" in
    user)
      gh api "users/$value" --jq '.id'
      ;;
    team)
      owner="${REPO%%/*}"
      gh api "orgs/$owner/teams/$value" --jq '.id'
      ;;
    *)
      die "unknown reviewer selector type: $kind"
      ;;
  esac
}

reviewers_json_from_selectors() {
  local selectors=("$@")
  local reviewers_json='[]'
  local selector normalized kind reviewer_id

  for selector in "${selectors[@]}"; do
    normalized="$(normalize_reviewer_selector "$selector")"
    kind="${normalized%%:*}"
    reviewer_id="$(resolve_reviewer_id "$normalized")"
    reviewers_json="$(jq -c \
      --arg type "${kind^}" \
      --argjson id "$reviewer_id" \
      '. + [{type:$type,id:$id}]' <<<"$reviewers_json")"
  done

  printf '%s' "$reviewers_json"
}

branch_policy_json() {
  local mode="$1"
  case "$mode" in
    none)
      printf 'null'
      ;;
    protected)
      printf '{"protected_branches":true,"custom_branch_policies":false}'
      ;;
    main|main-only)
      printf '{"protected_branches":false,"custom_branch_policies":true}'
      ;;
    *)
      die "branch policy must be none, protected, or main-only: $mode"
      ;;
  esac
}

clear_branch_policies() {
  local environment_name="$1"
  local policy_id

  while IFS= read -r policy_id; do
    [[ -n "$policy_id" ]] || continue
    gh api -X DELETE \
      -H "Accept: application/vnd.github+json" \
      -H "X-GitHub-Api-Version: ${GITHUB_API_VERSION}" \
      "repos/${REPO}/environments/${environment_name}/deployment-branch-policies/${policy_id}" >/dev/null
  done < <(gh api \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: ${GITHUB_API_VERSION}" \
    "repos/${REPO}/environments/${environment_name}/deployment-branch-policies" \
    --jq '.branch_policies[].id')
}

sync_branch_policy() {
  local environment_name="$1"
  local branch_policy_mode="$2"
  local branch_policy_name="$3"

  clear_branch_policies "$environment_name"

  case "$branch_policy_mode" in
    none)
      return 0
      ;;
    protected)
      return 0
      ;;
    main|main-only)
      [[ -n "$branch_policy_name" ]] || die "branch policy name is required for main-only mode"
      local payload
      payload="$(jq -n --arg name "$branch_policy_name" '{name:$name}')"
      printf '%s' "$payload" | gh api \
        -X POST \
        -H "Accept: application/vnd.github+json" \
        -H "X-GitHub-Api-Version: ${GITHUB_API_VERSION}" \
        "repos/${REPO}/environments/${environment_name}/deployment-branch-policies" \
        --input - >/dev/null
      echo "configured branch policy: ${environment_name} -> ${branch_policy_name}"
      ;;
    *)
      die "branch policy must be none, protected, or main-only: $branch_policy_mode"
      ;;
  esac
}

sync_environment_value() {
  local environment_name="$1"
  local kind="$2"
  local key="$3"
  local value="${4:-}"

  [[ -n "$value" ]] || {
    echo "skipped empty ${kind}: ${environment_name}/${key}"
    return 0
  }

  case "$kind" in
    secret)
      printf '%s' "$value" | gh secret set "$key" --repo "$REPO" --env "$environment_name" >/dev/null
      ;;
    variable)
      printf '%s' "$value" | gh variable set "$key" --repo "$REPO" --env "$environment_name" >/dev/null
      ;;
    *)
      die "unknown environment value kind: $kind"
      ;;
  esac
  echo "synced ${kind}: ${environment_name}/${key}"
}

sync_environment_values() {
  local environment_name="$1"
  local kind="$2"
  shift 2
  local key

  for key in "$@"; do
    sync_environment_value "$environment_name" "$kind" "$key" "${!key:-}"
  done
}

sync_staging_environment_values() {
  local key
  sync_environment_values "staging" variable \
    STAGING_REVIEWER \
    INCIDENT_OWNER \
    ESCALATION_ROUTE \
    WATCH_WINDOW

  for key in "${!LOADED_ENV_KEYS[@]}"; do
    case "$key" in
      REPO|GITHUB_API_VERSION|PREVENT_SELF_REVIEW|STAGING_BRANCH_POLICY|STAGING_BRANCH_NAME|PRODUCTION_BRANCH_POLICY|PRODUCTION_BRANCH_NAME|STAGING_REVIEWER|INCIDENT_OWNER|ESCALATION_ROUTE|WATCH_WINDOW|PRODUCTION_REVIEWER|PRODUCTION_APPROVER)
        continue
        ;;
    esac
    sync_environment_value "staging" secret "$key" "${!key:-}"
  done
}

sync_production_environment_values() {
  sync_environment_values "production" variable \
    PRODUCTION_APPROVER
}

set_environment_payload() {
  local environment_name="$1"
  local branch_policy_mode="$2"
  local branch_policy_name="$3"
  shift 3

  local reviewers_json='[]'
  if (($# > 0)); then
    reviewers_json="$(reviewers_json_from_selectors "$@")"
  fi

  local payload prevent_self_review_json deployment_branch_policy_json
  prevent_self_review_json="$(json_bool "$PREVENT_SELF_REVIEW")"
  deployment_branch_policy_json="$(branch_policy_json "$branch_policy_mode")"

  payload="$(jq -n \
    --argjson wait_timer 0 \
    --argjson prevent_self_review "$prevent_self_review_json" \
    --argjson reviewers "$reviewers_json" \
    --argjson deployment_branch_policy "$deployment_branch_policy_json" \
    '{wait_timer:$wait_timer,prevent_self_review:$prevent_self_review,reviewers:$reviewers,deployment_branch_policy:$deployment_branch_policy}')"

  printf '%s' "$payload" | gh api \
    -X PUT \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: ${GITHUB_API_VERSION}" \
    "repos/${REPO}/environments/${environment_name}" \
    --input - >/dev/null
  echo "configured environment: $environment_name"

  sync_branch_policy "$environment_name" "$branch_policy_mode" "$branch_policy_name"
}

main() {
  local -a env_files=()
  local -a staging_reviewers=()
  local -a production_reviewers=()

  while (($# > 0)); do
    case "$1" in
      --env-file)
        [[ $# -ge 2 ]] || die "--env-file requires a path"
        env_files+=("$2")
        shift 2
        ;;
      --staging-reviewer)
        [[ $# -ge 2 ]] || die "--staging-reviewer requires a selector"
        staging_reviewers+=("$2")
        shift 2
        ;;
      --production-reviewer)
        [[ $# -ge 2 ]] || die "--production-reviewer requires a selector"
        production_reviewers+=("$2")
        shift 2
        ;;
      -h|--help)
        usage
        return 0
        ;;
      *)
        die "unknown argument: $1"
        ;;
    esac
  done

  require_gh
  require_jq

  load_default_env_files
  local env_file
  for env_file in "${env_files[@]}"; do
    load_env_file "$env_file"
  done

  if ((${#staging_reviewers[@]} == 0)) && [[ -n "${STAGING_REVIEWER:-}" ]]; then
    staging_reviewers+=("$STAGING_REVIEWER")
  fi

  if ((${#production_reviewers[@]} == 0)); then
    if [[ -n "${PRODUCTION_REVIEWER:-}" ]]; then
      production_reviewers+=("$PRODUCTION_REVIEWER")
    elif [[ -n "${PRODUCTION_APPROVER:-}" ]]; then
      production_reviewers+=("$PRODUCTION_APPROVER")
    fi
  fi

  set_environment_payload "ci" none ""

  ((${#staging_reviewers[@]} > 0)) || die "at least one staging reviewer must be supplied"
  set_environment_payload "staging" "$STAGING_BRANCH_POLICY" "$STAGING_BRANCH_NAME" "${staging_reviewers[@]}"
  sync_staging_environment_values

  ((${#production_reviewers[@]} > 0)) || die "at least one production reviewer must be supplied"
  set_environment_payload "production" "$PRODUCTION_BRANCH_POLICY" "$PRODUCTION_BRANCH_NAME" "${production_reviewers[@]}"
  sync_production_environment_values

  cat <<EOF
Done.
  Repo: ${REPO}
  Loaded env files: .env .env.phase6 .env.phase6.server
  Staging branch policy: ${STAGING_BRANCH_POLICY}
  Staging branch name: ${STAGING_BRANCH_NAME}
  Production branch policy: ${PRODUCTION_BRANCH_POLICY}
  Production branch name: ${PRODUCTION_BRANCH_NAME}
  Prevent self review: ${PREVENT_SELF_REVIEW}
EOF
}

main "$@"
