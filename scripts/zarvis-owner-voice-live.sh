#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_VERSION="2026.08.07.3"
ROOT_DIR="${ZARVIS_REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
VOICE_ENV="$ROOT_DIR/.env.zarvis.voice.local"
VOICE_COMPOSE="$ROOT_DIR/compose.zarvis-owner-voice.yml"
LOCAL_ENV="$ROOT_DIR/.env.zarvis.local"
LOCAL_COMPOSE="$ROOT_DIR/compose.zarvis-local.yml"
DOMAIN_COMPOSE="$ROOT_DIR/compose.zarvis-owner-domain.yml"
CERT_DIR="$ROOT_DIR/.zarvis-owner-domain/certs"
STATE_DIR="$ROOT_DIR/.zarvis-owner-domain"
BUNDLE_DIR="$ROOT_DIR/zarvis-owner-domain-bundle"
VOICE_DOMAIN="voice.zarvis.zeaz.dev"
MODEL="${VOICE_LLM_MODEL:-qwen3:8b}"
VOICE_BOOTSTRAP_TIMEOUT_SECONDS="${VOICE_BOOTSTRAP_TIMEOUT_SECONDS:-3600}"
BOOTSTRAP_CONTAINERS=()

log(){ printf '[ZARVIS-VOICE] %s\n' "$*"; }
pass(){ printf '[ZARVIS-VOICE][PASS] %s\n' "$*"; }
die(){ printf '[ZARVIS-VOICE][ERROR] %s\n' "$*" >&2; exit 1; }
secret(){ openssl rand -base64 48 | tr -d '\n'; }

compose(){
  docker compose --env-file "$VOICE_ENV" -f "$VOICE_COMPOSE" "$@"
}

container_id(){
  compose ps -a -q "$1" | head -n 1
}

attach_bootstrap_egress(){
  local service="$1" cid
  cid="$(container_id "$service")"
  [[ -n "$cid" ]] || die "Could not resolve container for $service"
  docker network connect bridge "$cid" >/dev/null 2>&1 || true
  BOOTSTRAP_CONTAINERS+=("$cid")
}

seal_runtime_egress(){
  local cid
  for cid in "${BOOTSTRAP_CONTAINERS[@]}"; do
    docker network disconnect bridge "$cid" >/dev/null 2>&1 || true
  done
  BOOTSTRAP_CONTAINERS=()
}

wait_container_healthy(){
  local service="$1" timeout="$2" cid state health elapsed=0
  cid="$(container_id "$service")"
  [[ -n "$cid" ]] || die "Could not resolve container for $service"

  while (( elapsed < timeout )); do
    state="$(docker inspect --format '{{.State.Status}}' "$cid" 2>/dev/null || true)"
    health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null || true)"

    if [[ "$health" == healthy ]]; then
      return 0
    fi

    if [[ "$state" == exited || "$state" == dead ]]; then
      docker logs --tail 200 "$cid" >&2 || true
      die "$service exited during local model bootstrap"
    fi

    sleep 2
    elapsed=$((elapsed + 2))
  done

  docker logs --tail 200 "$cid" >&2 || true
  die "$service did not become healthy within bootstrap timeout"
}

trap seal_runtime_egress EXIT

for tool in docker curl openssl node python3 stat ss; do command -v "$tool" >/dev/null || die "$tool is required"; done
docker compose version >/dev/null 2>&1 || die 'Docker Compose plugin is required'
docker info >/dev/null 2>&1 || die 'Docker daemon unavailable'
[[ "$VOICE_BOOTSTRAP_TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || die 'VOICE_BOOTSTRAP_TIMEOUT_SECONDS must be an integer'
(( VOICE_BOOTSTRAP_TIMEOUT_SECONDS >= 300 )) || die 'VOICE_BOOTSTRAP_TIMEOUT_SECONDS must be at least 300 seconds'
[[ -f "$VOICE_COMPOSE" ]] || die "Missing $VOICE_COMPOSE"
[[ -f "$LOCAL_ENV" && -f "$LOCAL_COMPOSE" && -f "$DOMAIN_COMPOSE" ]] || die 'Run the owner-domain setup first'
[[ -s "$CERT_DIR/owner-ca.key" && -s "$CERT_DIR/owner-ca.crt" ]] || die 'Private owner CA is missing; run zarvis-owner-domain-setup.sh first'

if [[ ! -f "$VOICE_ENV" ]]; then
  umask 077
  cat >"$VOICE_ENV" <<EOF_ENV
Z_PLATFORM_SERVICE_TOKEN=$(secret)
VOICE_TICKET_SECRET=$(secret)
ZARVIS_EDGE_SHARED_SECRET=$(secret)
ZARVIS_ORCHESTRATOR_SERVICE_TOKEN=$(secret)
VOICE_PUBLIC_WS_URL=wss://$VOICE_DOMAIN/v1/realtime
VOICE_LLM_MODEL=$MODEL
VOICE_STT_BACKEND=faster-whisper
VOICE_STT_MODEL=small
VOICE_STT_LANGUAGE=th
VOICE_TTS_BACKEND=qwen3
VOICE_TTS_SPEAKER=Aiden
VOICE_TTS_DEVICE=cpu
OLLAMA_IMAGE=ollama/ollama:0.32.3
EOF_ENV
  chmod 600 "$VOICE_ENV"
fi
[[ "$(stat -c '%a' "$VOICE_ENV")" == 600 ]] || die "$VOICE_ENV must be mode 600"

log "Starting local Ollama runtime"
compose up -d ollama
attach_bootstrap_egress ollama
for _ in $(seq 1 60); do
  curl -fsS --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null || die 'Ollama did not become healthy'

log "Ensuring local model $MODEL"
if compose exec -T ollama ollama show "$MODEL" >/dev/null 2>&1; then
  pass "Local model $MODEL already present; skipping registry pull"
else
  log "Local model $MODEL not present; pulling during temporary bootstrap egress"
  compose exec -T ollama ollama pull "$MODEL"
fi

log "Building local voice runtime images"
compose build

log "Creating voice-agent before attaching temporary model-bootstrap egress"
compose rm -sf voice-agent >/dev/null 2>&1 || true
compose create voice-agent
attach_bootstrap_egress voice-agent
compose start voice-agent

log "Bootstrapping local STT/TTS models"
wait_container_healthy voice-agent "$VOICE_BOOTSTRAP_TIMEOUT_SECONDS"
pass 'voice-agent healthy with local STT/TTS models cached'

log "Starting owner orchestrator, voice gateway, ZVoice and owner edge"
compose up -d zarvis-orchestrator voice-gateway zvoice zarvis-owner-voice-edge

for endpoint in \
  http://127.0.0.1:8094/healthz \
  http://127.0.0.1:8450/health \
  http://127.0.0.1:3023/edge-healthz; do
  for _ in $(seq 1 180); do
    curl -fsS --max-time 5 "$endpoint" >/dev/null 2>&1 && break
    sleep 2
  done
  curl -fsS --max-time 5 "$endpoint" >/dev/null || die "Health check failed: $endpoint"
done
seal_runtime_egress
pass 'Standalone local voice services healthy; bootstrap egress detached'

log "Issuing owner certificate with voice domain SAN"
cat >"$STATE_DIR/server.ext" <<'EOF_EXT'
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=@alt_names

[alt_names]
DNS.1=zarvis.zeaz.dev
DNS.2=action.zarvis.zeaz.dev
DNS.3=proactive.zarvis.zeaz.dev
DNS.4=voice.zarvis.zeaz.dev
EOF_EXT
openssl genrsa -out "$CERT_DIR/server.key.new" 3072
chmod 600 "$CERT_DIR/server.key.new"
openssl req -new -sha256 -key "$CERT_DIR/server.key.new" -out "$CERT_DIR/server.csr.new" -subj '/CN=zarvis.zeaz.dev/O=ZEAZDEV COMPANY LIMITED'
openssl x509 -req -sha256 -days 397 \
  -in "$CERT_DIR/server.csr.new" \
  -CA "$CERT_DIR/owner-ca.crt" \
  -CAkey "$CERT_DIR/owner-ca.key" \
  -CAcreateserial \
  -out "$CERT_DIR/server.crt.new" \
  -extfile "$STATE_DIR/server.ext"
mv "$CERT_DIR/server.key.new" "$CERT_DIR/server.key"
mv "$CERT_DIR/server.crt.new" "$CERT_DIR/server.crt"
rm -f "$CERT_DIR/server.csr.new"
chmod 600 "$CERT_DIR/server.key"
chmod 644 "$CERT_DIR/server.crt"
openssl verify -CAfile "$CERT_DIR/owner-ca.crt" "$CERT_DIR/server.crt" >/dev/null
openssl x509 -in "$CERT_DIR/server.crt" -noout -ext subjectAltName | grep -F "$VOICE_DOMAIN" >/dev/null || die 'Voice SAN missing'

log 'Restarting loopback-only HTTPS gateway'
ZARVIS_OWNER_UID="$(id -u)" ZARVIS_OWNER_GID="$(id -g)" docker compose \
  --env-file "$LOCAL_ENV" \
  -f "$LOCAL_COMPOSE" \
  -f "$DOMAIN_COMPOSE" \
  up -d --force-recreate zarvis-owner-domain

for _ in $(seq 1 60); do
  curl -fsS --max-time 8 \
    --resolve "$VOICE_DOMAIN:8443:127.0.0.1" \
    --cacert "$CERT_DIR/owner-ca.crt" \
    "https://$VOICE_DOMAIN:8443/health" >/dev/null 2>&1 && break
  sleep 1
done
voice_health="$(curl -fsS --max-time 8 --resolve "$VOICE_DOMAIN:8443:127.0.0.1" --cacert "$CERT_DIR/owner-ca.crt" "https://$VOICE_DOMAIN:8443/health")"
node - "$voice_health" "$MODEL" <<'NODE'
const health = JSON.parse(process.argv[2]);
const expectedModel = process.argv[3];
if (
  health.status !== 'ok'
  || health.zarvis_owner_mode !== true
  || health.anonymous_access !== false
  || health.zarvis_bridge_configured !== true
  || health.local_conversation_configured !== true
  || health.local_llm_only !== true
  || health.local_llm_model !== expectedModel
) {
  throw new Error(`voice owner invariant failed: ${JSON.stringify(health)}`);
}
NODE
node "$ROOT_DIR/scripts/validate-zarvis-local-conversation.mjs" --runtime
pass 'TLS owner edge, local voice, orchestrator and loopback binding invariants'

mkdir -p "$BUNDLE_DIR/windows"
cp "$CERT_DIR/owner-ca.crt" "$BUNDLE_DIR/windows/zarvis-owner-ca.crt"
cp "$ROOT_DIR/apps/zarvis-windows/scripts/Install-ZARVIS-VoiceDomain.ps1" "$BUNDLE_DIR/windows/"
cat >"$BUNDLE_DIR/windows/Install-ZARVIS-VoiceDomain.cmd" <<'EOF_CMD'
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-ZARVIS-VoiceDomain.ps1"
pause
EOF_CMD
python3 - "$BUNDLE_DIR" <<'PY'
from pathlib import Path
import sys, zipfile
root = Path(sys.argv[1])
zip_path = root / 'zarvis-owner-domain-windows.zip'
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted((root / 'windows').rglob('*')):
        if path.is_file():
            archive.write(path, path.relative_to(root / 'windows'))
PY
chmod 600 "$BUNDLE_DIR/zarvis-owner-domain-windows.zip"

cat <<EOF_SUMMARY

============================================================
 Z.A.R.V.I.S. LOCAL CONVERSATION MODE: READY
============================================================
 Script:         $SCRIPT_VERSION
 Voice UI:       https://$VOICE_DOMAIN
 HTTPS gateway:  127.0.0.1:8443 only
 Voice edge:     127.0.0.1:3023 only
 Voice gateway:  127.0.0.1:8450 only
 Orchestrator:   127.0.0.1:8094 only
 LLM:            Ollama $MODEL (local)
 STT:            Faster Whisper (local)
 TTS:            local device voice in owner mode
 Runtime egress: detached after model bootstrap
 Public ingress: disabled
 Contract:       validated from Compose + nginx + live listeners

On Windows, extract the refreshed bundle and run:
  Install-ZARVIS-VoiceDomain.cmd
============================================================
EOF_SUMMARY
