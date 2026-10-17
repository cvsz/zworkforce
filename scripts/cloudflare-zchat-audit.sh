#!/usr/bin/env bash
# Read-only ZChat routing diagnostic owned by zWorkforce.
set -Eeuo pipefail

HOSTNAME="${ZCHAT_HOSTNAME:-zchat.zeaz.dev}"
CADDYFILE="${ZCHAT_CADDYFILE:-$HOME/.config/zwslcore-cloudflare/Caddyfile}"
MANIFEST="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/deploy/cloudflare/tunnel-ingress.yml"
ORIGIN="${ZCHAT_ORIGIN:-http://127.0.0.1:8000}"
CADDY="${ZCHAT_CADDY:-http://127.0.0.1}"
TUNNEL="${ZCHAT_TUNNEL:-zwslcore}"

case "$HOSTNAME" in zchat.zeaz.dev) ;; *) echo "Unexpected hostname; refusing check" >&2; exit 2;; esac
case "$ORIGIN" in http://127.0.0.1:* ) ;; *) echo "Origin must use loopback HTTP" >&2; exit 2;; esac
case "$CADDY" in http://127.0.0.1|http://127.0.0.1:80) ;; *) echo "Caddy must use local HTTP port 80" >&2; exit 2;; esac

printf '%s\n' '=== ZChat route audit (read-only; no credentials printed) ==='
printf 'Host: %s\nOrigin: %s\n' "$HOSTNAME" "$ORIGIN"
if [[ -f "$MANIFEST" ]]; then
  if grep -Eq "^[[:space:]]*-[[:space:]]*hostname:[[:space:]]*$HOSTNAME[[:space:]]*$" "$MANIFEST"; then
    echo "GitOps tunnel manifest: hostname is declared"
  else
    echo "GitOps tunnel manifest: hostname is MISSING (configuration drift)"
  fi
fi
if [[ -f "$CADDYFILE" ]]; then
  if grep -Fq "$HOSTNAME" "$CADDYFILE"; then
    echo "Caddyfile: hostname referenced"
  else
    echo "Caddyfile: hostname absent"
  fi
else
  echo "Caddyfile: not accessible"
fi
if command -v cloudflared >/dev/null 2>&1; then
  echo "=== Tunnel inventory ==="
  cloudflared tunnel info "$TUNNEL" 2>&1 | sed -E 's/(token|secret|password|credential)[=:][^[:space:]]+/\1=[REDACTED]/Ig' || true
fi

request() {
  local name="$1" url="$2" host_header="${3:-}"
  local status
  if [[ -n "$host_header" ]]; then
    status="$(curl --silent --show-error --location-trusted=false --max-time 12 -o /dev/null -w '%{http_code}' -H "Host: $host_header" "$url")" || status="NETWORK_ERROR"
  else
    status="$(curl --silent --show-error --max-time 12 -o /dev/null -w '%{http_code}' "$url")" || status="NETWORK_ERROR"
  fi
  printf '%-22s %s\n' "$name" "$status"
}
echo "=== HTTP status comparison ==="
request "public GET /" "https://$HOSTNAME/"
request "public GET /health" "https://$HOSTNAME/health"
request "local Caddy GET /" "$CADDY/" "$HOSTNAME"
request "origin GET /" "$ORIGIN/"
request "origin GET /health" "$ORIGIN/health"
echo "No DNS, Tunnel, Caddy, or application settings were changed."
