#!/usr/bin/env bash
set -Eeuo pipefail

HOST="${ZARVIS_ONLINE_HOST:-zarvis.zeaz.dev}"
HEALTH_PATH="${ZARVIS_ONLINE_HEALTH_PATH:-/health}"
ORIGIN_URL="${ZARVIS_ONLINE_ORIGIN_URL:-http://127.0.0.1:9570}"
CHECK_LOCAL_ORIGIN="${ZARVIS_CHECK_LOCAL_ORIGIN:-0}"

log() { printf '[zarvis-online] %s\n' "$*"; }
die() { printf '[zarvis-online][ERROR] %s\n' "$*" >&2; exit 1; }

require_2xx() {
  local url="$1"
  shift
  local status

  if ! status="$(
    curl --silent --show-error --output /dev/null \
      --write-out '%{http_code}' --max-redirs 0 \
      --connect-timeout 10 --max-time 20 "$@" "$url"
  )"; then
    die "HTTP request failed for $url"
  fi
  [[ "$status" =~ ^2[0-9][0-9]$ ]] || die "expected HTTP 2xx from $url, got $status"
}

command -v curl >/dev/null 2>&1 || die "curl is required"
command -v getent >/dev/null 2>&1 || die "getent is required"

if [[ "$HOST" == *://* || "$HOST" == */* || "$HOST" == *:* ]]; then
  die "ZARVIS_ONLINE_HOST must be a hostname only"
fi

log "resolving $HOST"
getent ahosts "$HOST" >/dev/null 2>&1 || die "DNS does not resolve for $HOST"

if [[ "$CHECK_LOCAL_ORIGIN" == "1" ]]; then
  log "checking local governed origin $ORIGIN_URL/health"
  require_2xx "$ORIGIN_URL/health"
fi

PUBLIC_HEALTH="https://${HOST}${HEALTH_PATH}"
log "checking public HTTPS health $PUBLIC_HEALTH"
require_2xx "$PUBLIC_HEALTH" --proto '=https' --tlsv1.2

log "checking public application route https://${HOST}/"
require_2xx "https://${HOST}/" --proto '=https' --tlsv1.2

log "PASS: Z.A.R.V.I.S. is online at https://${HOST}"
