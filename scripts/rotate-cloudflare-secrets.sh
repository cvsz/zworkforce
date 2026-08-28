#!/usr/bin/env bash
set -Eeuo pipefail

# This runner deliberately parses only Cloudflare variable names. It never
# sources the operator environment file and never writes secret values to
# stdout/stderr. Provider-specific hooks own the actual credential change.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${CLOUDFLARE_ENV_FILE:-$ROOT/.env.cloudflare}"
STATE_FILE="${ROTATION_STATE_FILE:-$ROOT/.rotation/cloudflare-rotation.json}"
HOOK_DIR="${ROTATION_HOOK_DIR:-$ROOT/scripts/cloudflare-rotation.d}"
OUT_DIR="${ROTATION_OUT_DIR:-$ROOT/output/cloudflare-rotation}"
ACTION=status

usage() {
  cat <<'USAGE'
Usage: rotate-cloudflare-secrets.sh [--status|--dry-run|--initialize|--execute]
  --env-file PATH   Operator environment file (default: .env.cloudflare)
  --state-file PATH Rotation metadata file (default: .rotation/cloudflare-rotation.json)
  --hook-dir PATH   Reviewed provider hooks (default: scripts/cloudflare-rotation.d)
  --out-dir PATH    Redacted rotation evidence directory

--execute is approval-gated: ROTATION_APPROVED=YES must be present. The runner
does not perform provider calls itself; executable *.sh hooks do that.
USAGE
}

fail() {
  printf 'cloudflare rotation: %s\n' "$1" >&2
  exit "${2:-1}"
}

while (($# > 0)); do
  case "$1" in
    --status|--dry-run)
      ACTION=status
      shift
      ;;
    --initialize)
      ACTION=initialize
      shift
      ;;
    --execute)
      ACTION=execute
      shift
      ;;
    --env-file|--state-file|--hook-dir|--out-dir)
      (($# >= 2)) || fail "missing value for $1" 2
      case "$1" in
        --env-file) ENV_FILE="$2" ;;
        --state-file) STATE_FILE="$2" ;;
        --hook-dir) HOOK_DIR="$2" ;;
        --out-dir) OUT_DIR="$2" ;;
      esac
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      fail "unknown option: $1" 2
      ;;
  esac
done

require_regular_secret_file() {
  local path="$1" label="$2" mode
  [[ -f "$path" && ! -L "$path" ]] || fail "$label must be a regular file: $path"
  mode="$(stat -c '%a' "$path")"
  (( (8#$mode & 8#077) == 0 )) || {
    fail "$label must not be group/world accessible: $path (run chmod 600)"
  }
}

require_regular_secret_file "$ENV_FILE" "Cloudflare environment"

read_interval_days() {
  local value
  value="$(awk -F= '
    /^[[:space:]]*(export[[:space:]]+)?CLOUDFLARE_ROTATION_INTERVAL_DAYS[[:space:]]*=/ {
      sub(/^[^=]*=[[:space:]]*/, "", $0)
      gsub(/[[:space:]]+$/, "", $0)
      gsub(/^['\"]|['\"]$/, "", $0)
      print $0
      exit
    }
  ' "$ENV_FILE")"
  [[ -n "$value" ]] || value=30
  [[ "$value" =~ ^[0-9]+$ ]] || fail "CLOUDFLARE_ROTATION_INTERVAL_DAYS must be an integer"
  (( value >= 1 && value <= 3650 )) || fail "rotation interval must be between 1 and 3650 days"
  printf '%s\n' "$value"
}

mapfile -t CLOUDFLARE_SECRET_NAMES < <(
  awk -F= '
    /^[[:space:]]*(export[[:space:]]+)?CLOUDFLARE_[A-Za-z0-9_]+[[:space:]]*=/ {
      key=$1
      sub(/^[[:space:]]*(export[[:space:]]+)?/, "", key)
      gsub(/[[:space:]]+$/, "", key)
      if (key ~ /(_TOKEN|_KEY_ID|_SECRET|_PASSWORD)$/ || key ~ /_SECRET_/) print key
    }
  ' "$ENV_FILE" | sort -u
)

INTERVAL_DAYS="$(read_interval_days)"
INTERVAL_SECONDS=$((INTERVAL_DAYS * 24 * 60 * 60))

state_value() {
  local key="$1"
  [[ -f "$STATE_FILE" && ! -L "$STATE_FILE" ]] || return 1
  jq -er --arg key "$key" '.[$key]' "$STATE_FILE"
}

state_status() {
  local now="$1" next
  next="$(state_value next_rotation_epoch 2>/dev/null || true)"
  if [[ -z "$next" ]]; then
    printf 'uninitialized\n'
  elif (( now >= next )); then
    printf 'due\n'
  else
    printf 'scheduled\n'
  fi
}

write_state() {
  local last_epoch="$1" next_epoch="$2" reason="$3"
  local state_dir temp_file secret_names_json
  state_dir="$(dirname "$STATE_FILE")"
  secret_names_json="$(printf '%s\n' "${CLOUDFLARE_SECRET_NAMES[@]}" | jq -Rsc 'split("\n") | map(select(length > 0))')"

  umask 077
  mkdir -p "$state_dir"
  chmod 700 "$state_dir"
  temp_file="$(mktemp "$state_dir/.cloudflare-rotation.XXXXXX")"
  jq -n \
    --arg env_file "$ENV_FILE" \
    --arg reason "$reason" \
    --argjson interval_days "$INTERVAL_DAYS" \
    --argjson last_rotation_epoch "$last_epoch" \
    --argjson next_rotation_epoch "$next_epoch" \
    --argjson secret_names "$secret_names_json" \
    '{schema: 1, env_file: $env_file, interval_days: $interval_days,
      last_rotation_epoch: $last_rotation_epoch,
      next_rotation_epoch: $next_rotation_epoch,
      baseline_reason: $reason, secret_names: $secret_names}' > "$temp_file"
  chmod 600 "$temp_file"
  mv -f "$temp_file" "$STATE_FILE"
}

print_inventory() {
  printf 'env_file=%s\n' "$ENV_FILE"
  printf 'interval_days=%s\n' "$INTERVAL_DAYS"
  if ((${#CLOUDFLARE_SECRET_NAMES[@]} == 0)); then
    printf 'secret_names=none-detected\n'
  else
    printf 'secret_name=%s\n' "${CLOUDFLARE_SECRET_NAMES[@]}"
  fi
}

case "$ACTION" in
  initialize)
    last_epoch="$(stat -c '%Y' "$ENV_FILE")"
    write_state "$last_epoch" "$((last_epoch + INTERVAL_SECONDS))" "env-file-mtime"
    printf 'status=initialized\nlast_rotation_epoch=%s\nnext_rotation_epoch=%s\n' \
      "$last_epoch" "$((last_epoch + INTERVAL_SECONDS))"
    print_inventory
    ;;
  status)
    now="$(date +%s)"
    printf 'status=%s\n' "$(state_status "$now")"
    if [[ -f "$STATE_FILE" && ! -L "$STATE_FILE" ]]; then
      printf 'last_rotation_epoch=%s\n' "$(state_value last_rotation_epoch)"
      printf 'next_rotation_epoch=%s\n' "$(state_value next_rotation_epoch)"
    else
      printf 'baseline_epoch=%s\n' "$(stat -c '%Y' "$ENV_FILE")"
    fi
    print_inventory
    ;;
  execute)
    [[ "${ROTATION_APPROVED:-}" == YES ]] || {
      printf 'cloudflare rotation: --execute requires ROTATION_APPROVED=YES\n' >&2
      exit 3
    }
    [[ -f "$STATE_FILE" && ! -L "$STATE_FILE" ]] || {
      fail "rotation is not initialized; run --initialize first" 4
    }
    now="$(date +%s)"
    next_epoch="$(state_value next_rotation_epoch)"
    (( now >= next_epoch )) || {
      printf 'status=not-due\nnext_rotation_epoch=%s\n' "$next_epoch"
      print_inventory
      exit 0
    }

    mapfile -t hooks < <(find "$HOOK_DIR" -maxdepth 1 -type f -name '*.sh' -perm /111 -print 2>/dev/null | sort)
    ((${#hooks[@]} > 0)) || fail "no executable reviewed hooks found in $HOOK_DIR" 4

    umask 077
    mkdir -p "$OUT_DIR"
    chmod 700 "$OUT_DIR"
    for hook in "${hooks[@]}"; do
      hook_name="$(basename "$hook")"
      printf 'running_hook=%s\n' "$hook_name"
      if ! ROTATION_ENV_FILE="$ENV_FILE" ROTATION_OUT_DIR="$OUT_DIR" \
        "$hook" "$ENV_FILE" >/dev/null 2>&1; then
        printf 'cloudflare rotation: hook failed: %s\n' "$hook_name" >&2
        exit 5
      fi
    done

    write_state "$now" "$((now + INTERVAL_SECONDS))" "approved-hook-execution"
    printf 'status=rotated\nlast_rotation_epoch=%s\nnext_rotation_epoch=%s\n' \
      "$now" "$((now + INTERVAL_SECONDS))"
    print_inventory
    ;;
esac
