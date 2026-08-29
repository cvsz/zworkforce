#!/usr/bin/env bash
set -euo pipefail

voice_gateway_url="${VOICE_GATEWAY_HTTP_URL:-http://127.0.0.1:8450}"
zvoice_url="${ZVOICE_URL:-http://127.0.0.1:3022}"

curl --fail --silent --show-error "${voice_gateway_url}/health" | python3 -m json.tool
curl --fail --silent --show-error "${zvoice_url}/health/live" | python3 -m json.tool

ticket_json="$(
  curl --fail --silent --show-error \
    -X POST "${voice_gateway_url}/v1/voice/tickets" \
    -H "Authorization: Bearer ${Z_PLATFORM_SERVICE_TOKEN:?Z_PLATFORM_SERVICE_TOKEN is required}" \
    -H "X-Tenant-Id: smoke-test" \
    -H "X-Subject-Id: smoke-test" \
    -H "Content-Type: application/json" \
    -d '{}'
)"

python3 - "${ticket_json}" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
assert payload["ticket"]
assert payload["websocket_url"].endswith("/v1/realtime")
assert payload["ticket_transport"] == "sec-websocket-protocol"
print("voice ticket contract: ok")
PY

echo "HTTP and ticket smoke checks passed."
echo "Run the browser test at ${zvoice_url} to validate microphone capture, interruption, transcription, and audio playback."
