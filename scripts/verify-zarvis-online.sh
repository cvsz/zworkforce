#!/usr/bin/env bash
set -Eeuo pipefail

HOST="${ZARVIS_ONLINE_HOST:-zarvis.zeaz.dev}"
HEALTH_PATH="${ZARVIS_ONLINE_HEALTH_PATH:-/health}"
ORIGIN_URL="${ZARVIS_ONLINE_ORIGIN_URL:-http://127.0.0.1:9570}"
CHECK_LOCAL_ORIGIN="${ZARVIS_CHECK_LOCAL_ORIGIN:-0}"

log() { printf '[zarvis-online] %s\n' "$*"; }
die() { printf '[zarvis-online][ERROR] %s\n' "$*" >&2; exit 1; }

command -v curl >/dev/null 2>&1 || die "curl is required"
command -v getent >/dev/null 2>&1 || die "getent is required"

if [[ "$HOST" == *://* || "$HOST" == */* || "$HOST" == *:* ]]; then
  die "ZARVIS_ONLINE_HOST must be a hostname only"
fi

log "resolving $HOST"
getent ahosts "$HOST" >/dev/null 2>&1 || die "DNS does not resolve for $HOST"

if [[ "$CHECK_LOCAL_ORIGIN" == "1" ]]; then
  log "checking local governed origin $ORIGIN_URL/health"
  curl --fail --silent --show-error \
    --connect-timeout 5 --max-time 15 \
    "$ORIGIN_URL/health" >/dev/null || die "local origin health failed"
fi

PUBLIC_HEALTH="https://${HOST}${HEALTH_PATH}"
log "checking public HTTPS health $PUBLIC_HEALTH"
curl --fail --silent --show-error \
  --proto '=https' --tlsv1.2 \
  --connect-timeout 10 --max-time 20 \
  "$PUBLIC_HEALTH" >/dev/null || die "public Z.A.R.V.I.S. health failed"

log "checking public application route https://${HOST}/"
curl --fail --silent --show-error \
  --proto '=https' --tlsv1.2 \
  --connect-timeout 10 --max-time 20 \
  -o /dev/null "https://${HOST}/" || die "public Z.A.R.V.I.S. application route failed"

log "PASS: Z.A.R.V.I.S. is online at https://${HOST}"
