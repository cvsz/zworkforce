#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load .env.ai if present
if [ -f "$ROOT/.env.ai" ]; then
  set -a
  source "$ROOT/.env.ai"
  set +a
fi

export ZWORKFORCE_ZARVIS_VOICE_ENABLED="${ZWORKFORCE_ZARVIS_VOICE_ENABLED:-true}"
export ZWORKFORCE_ZARVIS_VOICE_GATEWAY_URL="${ZWORKFORCE_ZARVIS_VOICE_GATEWAY_URL:-http://127.0.0.1:8450}"
export ZWORKFORCE_ZARVIS_VOICE_SERVICE_TOKEN="${ZWORKFORCE_ZARVIS_VOICE_SERVICE_TOKEN:-${Z_PLATFORM_SERVICE_TOKEN:-}}"
if [[ "${ZWORKFORCE_ZARVIS_VOICE_ENABLED,,}" =~ ^(1|true|yes|on)$ ]]; then
  # Match the runtime's minimum length rule without printing token material.
  voice_token_non_whitespace="${ZWORKFORCE_ZARVIS_VOICE_SERVICE_TOKEN//[[:space:]]/}"
  if [[ ${#voice_token_non_whitespace} -lt 32 ]]; then
    unset voice_token_non_whitespace
    echo "ZWORKFORCE_ZARVIS_VOICE_SERVICE_TOKEN must be provisioned (at least 32 non-whitespace characters) when voice is enabled; no default token is provided." >&2
    exit 1
  fi
  unset voice_token_non_whitespace
fi
export ZWORKFORCE_ZARVIS_VOICE_WS_ALLOWLIST="${ZWORKFORCE_ZARVIS_VOICE_WS_ALLOWLIST:-ws://127.0.0.1:8450,ws://127.0.0.1:8765,wss://voice.zarvis.zeaz.dev,wss://zai.zeaz.dev}"
export ZWORKFORCE_ZARVIS_VOICE_MODEL="${ZWORKFORCE_ZARVIS_VOICE_MODEL:-qwen3:8b}"

if [[ "${ZWORKFORCE_ZARVIS_VOICE_ENABLED,,}" =~ ^(1|true|yes|on)$ ]]; then
  echo "Starting zWorkforce with Z.A.R.V.I.S. Voice Enabled..."
else
  echo "Starting zWorkforce with Z.A.R.V.I.S. Voice Disabled..."
fi
exec python3 -m zworkforce.cli serve
