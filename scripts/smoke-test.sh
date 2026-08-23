#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${ZWORKFORCE_BASE_URL:-http://127.0.0.1:9569}"
CURL=(curl --fail --silent --show-error --connect-timeout 5 --max-time 15)

check_json_field() {
  local url="$1" field="$2" expected="$3"
  local body
  body="$("${CURL[@]}" "$url")"
  PY_BIN="$(command -v python3 || command -v python)"
  BODY="$body" FIELD="$field" EXPECTED="$expected" "$PY_BIN" - <<'PY'
import json, os

data = json.loads(os.environ["BODY"])
actual = data
for part in os.environ["FIELD"].split("."):
    actual = actual[part]
expected = os.environ["EXPECTED"]
if str(actual).lower() != expected.lower():
    raise SystemExit(f"{os.environ['FIELD']}={actual!r}, expected {expected!r}")
PY
}

check_json_field "${BASE_URL}/health" status ok
"${CURL[@]}" "${BASE_URL}/ready" >/dev/null

if [[ -n "${ZWORKFORCE_API_KEY:-}" ]]; then
  "${CURL[@]}" \
    -H "Authorization: Bearer ${ZWORKFORCE_API_KEY}" \
    "${BASE_URL}/api/v1/overview" >/dev/null
fi

echo "smoke test passed: ${BASE_URL}"
