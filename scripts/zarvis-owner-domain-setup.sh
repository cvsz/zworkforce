#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_VERSION="2026.08.07.1"
ROOT_DIR="${ZARVIS_REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ENV_FILE="$ROOT_DIR/.env.zarvis.local"
LOCAL_COMPOSE="$ROOT_DIR/compose.zarvis-local.yml"
DOMAIN_COMPOSE="$ROOT_DIR/compose.zarvis-owner-domain.yml"
STATE_DIR="$ROOT_DIR/.zarvis-owner-domain"
CERT_DIR="$STATE_DIR/certs"
BUNDLE_DIR="$ROOT_DIR/zarvis-owner-domain-bundle"
DOMAIN="zarvis.zeaz.dev"
ACTION_DOMAIN="action.zarvis.zeaz.dev"
PROACTIVE_DOMAIN="proactive.zarvis.zeaz.dev"
SSH_USER="${USER}"
SSH_PORT=22
SERVER_HOST=""
ROTATE_CA=false

log()  { printf '[ZARVIS-DOMAIN] %s\n' "$*"; }
pass() { printf '[ZARVIS-DOMAIN][PASS] %s\n' "$*"; }
warn() { printf '[ZARVIS-DOMAIN][WARN] %s\n' "$*" >&2; }
die()  { printf '[ZARVIS-DOMAIN][ERROR] %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'USAGE'
Owner-only HTTPS domain setup for the local Z.A.R.V.I.S. runtime

Usage:
  bash scripts/zarvis-owner-domain-setup.sh [options]

Options:
  --server-host HOST  Private LAN or Tailscale address used by Windows SSH.
  --ssh-user USER     SSH user (default: current Linux user).
  --ssh-port PORT     SSH port (default: 22).
  --rotate-ca         Replace the private owner CA and leaf certificate.
  -h, --help          Show this help.

The service remains bound to Linux loopback. No public DNS record, router
forwarding, public reverse proxy, or Cloudflare Tunnel is created.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --server-host)
      [[ $# -ge 2 ]] || die "--server-host requires a value"
      SERVER_HOST="$2"
      shift 2
      ;;
    --ssh-user)
      [[ $# -ge 2 ]] || die "--ssh-user requires a value"
      SSH_USER="$2"
      shift 2
      ;;
    --ssh-port)
      [[ $# -ge 2 ]] || die "--ssh-port requires a value"
      SSH_PORT="$2"
      shift 2
      ;;
    --rotate-ca)
      ROTATE_CA=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

[[ "$SSH_PORT" =~ ^[0-9]+$ ]] && (( SSH_PORT >= 1 && SSH_PORT <= 65535 )) ||
  die "SSH port must be between 1 and 65535"
[[ "$SSH_USER" =~ ^[A-Za-z_][A-Za-z0-9._-]*$ ]] || die "Invalid SSH user"

for tool in docker curl openssl node python3 sed awk grep stat hostname ss; do
  command -v "$tool" >/dev/null 2>&1 || die "$tool is required"
done
docker compose version >/dev/null 2>&1 || die "Docker Compose plugin is required"
docker info >/dev/null 2>&1 || die "Docker daemon unavailable or permission denied"

[[ -f "$ENV_FILE" ]] || die "Missing $ENV_FILE; run zarvis-local-setup.sh first"
[[ -f "$LOCAL_COMPOSE" ]] || die "Missing compose.zarvis-local.yml"
[[ -f "$DOMAIN_COMPOSE" ]] || die "Missing compose.zarvis-owner-domain.yml"
[[ "$(stat -c '%a' "$ENV_FILE")" == "600" ]] || die "$ENV_FILE must be mode 600"

if [[ -z "$SERVER_HOST" ]] && command -v tailscale >/dev/null 2>&1; then
  SERVER_HOST="$(tailscale ip -4 2>/dev/null | head -n 1 || true)"
fi
if [[ -z "$SERVER_HOST" ]]; then
  SERVER_HOST="$(hostname -I 2>/dev/null | awk '{print $1}')"
fi
[[ -n "$SERVER_HOST" ]] || die "Could not detect a private server address; use --server-host"
[[ "$SERVER_HOST" =~ ^[A-Za-z0-9._:-]+$ ]] || die "Invalid server host"

mkdir -p "$CERT_DIR" "$BUNDLE_DIR"
chmod 700 "$STATE_DIR" "$CERT_DIR" "$BUNDLE_DIR"

for pattern in '/.zarvis-owner-domain/' '/zarvis-owner-domain-bundle/'; do
  grep -qxF "$pattern" "$ROOT_DIR/.git/info/exclude" 2>/dev/null ||
    printf '%s\n' "$pattern" >>"$ROOT_DIR/.git/info/exclude"
done

if [[ "$ROTATE_CA" == true ]]; then
  rm -f "$CERT_DIR/owner-ca.key" "$CERT_DIR/owner-ca.crt"
  rm -f "$CERT_DIR/server.key" "$CERT_DIR/server.csr" "$CERT_DIR/server.crt"
fi

if [[ ! -s "$CERT_DIR/owner-ca.key" || ! -s "$CERT_DIR/owner-ca.crt" ]]; then
  log "Generating private owner CA"
  openssl genrsa -out "$CERT_DIR/owner-ca.key" 4096
  chmod 600 "$CERT_DIR/owner-ca.key"
  openssl req -x509 -new -sha256 -days 3650 \
    -key "$CERT_DIR/owner-ca.key" \
    -out "$CERT_DIR/owner-ca.crt" \
    -subj "/CN=ZARVIS Owner Root CA/O=ZEAZDEV COMPANY LIMITED"
  chmod 644 "$CERT_DIR/owner-ca.crt"
fi

needs_leaf=true
if [[ -s "$CERT_DIR/server.key" && -s "$CERT_DIR/server.crt" ]] &&
   openssl x509 -checkend 2592000 -noout -in "$CERT_DIR/server.crt" >/dev/null 2>&1; then
  needs_leaf=false
fi

if [[ "$needs_leaf" == true ]]; then
  log "Generating private HTTPS certificate"
  cat >"$STATE_DIR/server.ext" <<EOF_EXT
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=@alt_names

[alt_names]
DNS.1=$DOMAIN
DNS.2=$ACTION_DOMAIN
DNS.3=$PROACTIVE_DOMAIN
EOF_EXT
  openssl genrsa -out "$CERT_DIR/server.key" 3072
  chmod 600 "$CERT_DIR/server.key"
  openssl req -new -sha256 \
    -key "$CERT_DIR/server.key" \
    -out "$CERT_DIR/server.csr" \
    -subj "/CN=$DOMAIN/O=ZEAZDEV COMPANY LIMITED"
  openssl x509 -req -sha256 -days 397 \
    -in "$CERT_DIR/server.csr" \
    -CA "$CERT_DIR/owner-ca.crt" \
    -CAkey "$CERT_DIR/owner-ca.key" \
    -CAcreateserial \
    -out "$CERT_DIR/server.crt" \
    -extfile "$STATE_DIR/server.ext"
  chmod 644 "$CERT_DIR/server.crt"
fi

openssl verify -CAfile "$CERT_DIR/owner-ca.crt" "$CERT_DIR/server.crt" >/dev/null
openssl x509 -in "$CERT_DIR/server.crt" -noout -ext subjectAltName |
  grep -F "$DOMAIN" >/dev/null ||
  die "Leaf certificate SAN validation failed"

log "Starting loopback-only HTTPS owner gateway"
docker compose \
  --env-file "$ENV_FILE" \
  -f "$LOCAL_COMPOSE" \
  -f "$DOMAIN_COMPOSE" \
  up -d zarvis-owner-domain

for _ in $(seq 1 60); do
  if curl -fsS --max-time 5 \
    --resolve "$DOMAIN:8443:127.0.0.1" \
    --cacert "$CERT_DIR/owner-ca.crt" \
    "https://$DOMAIN:8443/healthz" >/dev/null &&
     curl -fsS --max-time 5 \
    --resolve "$PROACTIVE_DOMAIN:8443:127.0.0.1" \
    --cacert "$CERT_DIR/owner-ca.crt" \
    "https://$PROACTIVE_DOMAIN:8443/healthz" >/dev/null; then
    break
  fi
  sleep 1
done

action_health="$(
  curl -fsS --max-time 5 \
    --resolve "$DOMAIN:8443:127.0.0.1" \
    --cacert "$CERT_DIR/owner-ca.crt" \
    "https://$DOMAIN:8443/healthz"
)"
proactive_health="$(
  curl -fsS --max-time 5 \
    --resolve "$PROACTIVE_DOMAIN:8443:127.0.0.1" \
    --cacert "$CERT_DIR/owner-ca.crt" \
    "https://$PROACTIVE_DOMAIN:8443/healthz"
)"

node - "$action_health" "$proactive_health" <<'NODE'
for (const raw of process.argv.slice(2)) {
  const value = JSON.parse(raw);
  if (value.status !== 'ok' || value.local_only !== true || value.secrets_exposed !== false) {
    throw new Error('owner-domain health invariant failed');
  }
}
NODE
pass "HTTPS proxy health and owner-only invariants"

listeners="$(ss -ltnH | awk '$4 ~ /:8443$/ {print $4}')"
[[ -n "$listeners" ]] || die "HTTPS gateway is not listening"
while IFS= read -r address; do
  [[ "$address" == 127.0.0.1:8443 || "$address" == "[::1]":8443 || "$address" == ::1:8443 ]] ||
    die "Owner gateway exposed on non-loopback address: $address"
done <<<"$listeners"
pass "HTTPS gateway bound only to loopback"

rm -rf "$BUNDLE_DIR/windows"
mkdir -p "$BUNDLE_DIR/windows"
cp "$CERT_DIR/owner-ca.crt" "$BUNDLE_DIR/windows/zarvis-owner-ca.crt"
cp "$ROOT_DIR/apps/zarvis-windows/scripts/Install-ZARVIS-OwnerDomain.ps1" "$BUNDLE_DIR/windows/"
cp "$ROOT_DIR/apps/zarvis-windows/scripts/Uninstall-ZARVIS-OwnerDomain.ps1" "$BUNDLE_DIR/windows/"

cat >"$BUNDLE_DIR/windows/Install-ZARVIS-OwnerDomain.cmd" <<EOF_CMD
@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-ZARVIS-OwnerDomain.ps1" -ServerHost "$SERVER_HOST" -SshUser "$SSH_USER" -SshPort $SSH_PORT
echo.
pause
EOF_CMD

cat >"$BUNDLE_DIR/windows/README.txt" <<EOF_README
Z.A.R.V.I.S. Owner Domain

Primary console:
  https://$DOMAIN

Proactive console:
  https://$PROACTIVE_DOMAIN

Security:
  - Linux HTTPS gateway listens only on 127.0.0.1:8443.
  - Windows forwards only 127.0.0.1:443 over encrypted SSH.
  - These names are mapped only in the owner's Windows hosts file.
  - No public DNS record or public HTTP ingress is required.
  - Owner Token remains required by the Z.A.R.V.I.S. console.
  - The private CA key stays on the Linux server and is not in this bundle.

Install:
  Double-click Install-ZARVIS-OwnerDomain.cmd.
  Enter the Linux SSH password once only when the installer needs to authorize
  the generated Windows SSH key.

Uninstall:
  Run PowerShell as Administrator:
  powershell -ExecutionPolicy Bypass -File .\Uninstall-ZARVIS-OwnerDomain.ps1
EOF_README

python3 - "$BUNDLE_DIR" <<'PY'
from pathlib import Path
import sys, zipfile
root = Path(sys.argv[1])
zip_path = root / "zarvis-owner-domain-windows.zip"
if zip_path.exists():
    zip_path.unlink()
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted((root / "windows").rglob("*")):
        if path.is_file():
            archive.write(path, path.relative_to(root / "windows"))
PY
chmod 600 "$BUNDLE_DIR/zarvis-owner-domain-windows.zip"

ca_fingerprint="$(openssl x509 -in "$CERT_DIR/owner-ca.crt" -noout -fingerprint -sha256 | cut -d= -f2)"
cat >"$BUNDLE_DIR/deployment.json" <<EOF_JSON
{
  "schema_version": "zarvis.owner-domain.v1",
  "generated_at": "$(date --iso-8601=seconds)",
  "owner_github_id": "4076926",
  "primary_domain": "$DOMAIN",
  "action_domain": "$ACTION_DOMAIN",
  "proactive_domain": "$PROACTIVE_DOMAIN",
  "server_host": "$SERVER_HOST",
  "ssh_user": "$SSH_USER",
  "ssh_port": $SSH_PORT,
  "linux_listener": "127.0.0.1:8443",
  "windows_listener": "127.0.0.1:443",
  "public_dns_required": false,
  "public_http_ingress": false,
  "private_ca_sha256_fingerprint": "$ca_fingerprint"
}
EOF_JSON
chmod 600 "$BUNDLE_DIR/deployment.json"

cat <<EOF_SUMMARY

============================================================
 Z.A.R.V.I.S. OWNER DOMAIN: READY
============================================================
 Primary:    https://$DOMAIN
 Proactive:  https://$PROACTIVE_DOMAIN
 Server:     127.0.0.1:8443 only
 SSH target: $SSH_USER@$SERVER_HOST:$SSH_PORT
 Bundle:     $BUNDLE_DIR/zarvis-owner-domain-windows.zip

From Windows PowerShell:
  scp -P $SSH_PORT $SSH_USER@${SERVER_HOST}:$BUNDLE_DIR/zarvis-owner-domain-windows.zip \$env:USERPROFILE\\Downloads\\

Extract the ZIP, then double-click:
  Install-ZARVIS-OwnerDomain.cmd

No public DNS or public web ingress was created.
============================================================
EOF_SUMMARY
