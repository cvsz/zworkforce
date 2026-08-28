#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load .env.ai if present
if [ -f "$ROOT/.env.ai" ]; then
  set -a
  source "$ROOT/.env.ai"
  set +a
fi

export ZWORKFORCE_ZARVIS_VOICE_ENABLED="true"
export ZWORKFORCE_ZARVIS_VOICE_GATEWAY_URL="${ZWORKFORCE_ZARVIS_VOICE_GATEWAY_URL:-http://127.0.0.1:8450}"
export ZWORKFORCE_ZARVIS_VOICE_SERVICE_TOKEN="${ZWORKFORCE_ZARVIS_VOICE_SERVICE_TOKEN:-${Z_PLATFORM_SERVICE_TOKEN:-8a21dacd9d8136b620dc4ba02da4660788de5e2d25b98b920585d189a443e097}}"
export ZWORKFORCE_ZARVIS_VOICE_WS_ALLOWLIST="${ZWORKFORCE_ZARVIS_VOICE_WS_ALLOWLIST:-ws://127.0.0.1:8450,ws://127.0.0.1:8765,wss://voice.zarvis.zeaz.dev,wss://zai.zeaz.dev}"
export ZWORKFORCE_ZARVIS_VOICE_MODEL="${ZWORKFORCE_ZARVIS_VOICE_MODEL:-qwen3:8b}"

echo "Starting zWorkforce with Z.A.R.V.I.S. Voice Enabled..."
exec python3 -m zworkforce.cli serve
