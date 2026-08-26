#!/usr/bin/env bash
set -euo pipefail

# zWorkforce v3.0.4 Observability release verification (Stage G)
# PASS requires both runtime scrape targets, Alertmanager routing receipt, and
# a synthetic trace observed by the external OTel Collector.

PROM_API="${PROMETHEUS_API_URL:-http://127.0.0.1:19090}"
OBS_HOST="${OBS_HOST:?set OBS_HOST (ssh target hosting observability stack)}"
OBS_DEPLOY_DIR="${OBS_DEPLOY_DIR:-/opt/zworkforce-observability}"
OBS_COMPOSE_FILE="${OBS_COMPOSE_FILE:-compose.vm-b.yaml}"
ALERTMANAGER_PORT="${ALERTMANAGER_PORT:-19093}"
ALERT_RECEIVER_TEST_URL="${ALERT_RECEIVER_TEST_URL:?set ALERT_RECEIVER_TEST_URL receipt endpoint}"
ALERT_RECEIVER_TOKEN_FILE="${ALERT_RECEIVER_TOKEN_FILE:?set ALERT_RECEIVER_TOKEN_FILE for receipt authorization}"

[[ -r "$ALERT_RECEIVER_TOKEN_FILE" ]] || {
  echo "VERIFY-OBS: FAIL: alert receiver token file is not readable" >&2
  exit 1
}
receiver_token="$(<"$ALERT_RECEIVER_TOKEN_FILE")"
[[ -n "$receiver_token" ]] || {
  echo "VERIFY-OBS: FAIL: alert receiver token file is empty" >&2
  exit 1
}

fail(){ echo "VERIFY-OBS: FAIL: $*" >&2; exit 1; }
note(){ echo "VERIFY-OBS: $*"; }

collector_logs(){
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$OBS_HOST" \
    "cd '$OBS_DEPLOY_DIR' && docker compose -f '$OBS_COMPOSE_FILE' logs --no-color --since 5m otel-collector 2>&1"
}

safe_host(){
  python3 - "$1" <<'PY'
import sys
from urllib.parse import urlsplit
u=urlsplit(sys.argv[1])
print(u.hostname or 'unknown-host')
PY
}

note "checking Prometheus targets"
targets=""
targets_ready=0
for _ in $(seq 1 12); do
  targets="$(curl -fsS "${PROM_API}/api/v1/targets" 2>/dev/null || true)"
  if [[ -n "$targets" ]] && echo "$targets" | python3 -c '
import json, sys
d=json.load(sys.stdin)
jobs={t.get("labels",{}).get("job"): t.get("health") for t in d["data"]["activeTargets"]}
required=("zworkforce-vm-a","zworkforce-vm-b","otel-collector")
missing=[j for j in required if jobs.get(j)!="up"]
if missing:
    raise SystemExit(1)
'; then
    targets_ready=1
    break
  fi
  sleep 5
done
[[ "$targets_ready" -eq 1 ]] || fail "Prometheus does not have all required targets UP after bounded polling"
note "Prometheus targets UP: vm-a, vm-b, otel-collector"

metrics_resp="$(curl -fsS --get "${PROM_API}/api/v1/query" --data-urlencode 'query=up{job=~"zworkforce-vm-(a|b)"} == 1' || fail "metrics query failed")"
echo "$metrics_resp" | python3 -c '
import json, sys
d=json.load(sys.stdin)
jobs={r.get("metric",{}).get("job") for r in d["data"]["result"]}
required={"zworkforce-vm-a","zworkforce-vm-b"}
if not required.issubset(jobs):
    raise SystemExit(1)
' || fail "metrics query does not prove both runtime targets"

note "checking Alertmanager readiness on published port ${ALERTMANAGER_PORT}"
ssh -o BatchMode=yes -o ConnectTimeout=10 "$OBS_HOST" \
  "curl -fsS http://127.0.0.1:${ALERTMANAGER_PORT}/-/ready >/dev/null" || fail "Alertmanager not ready"

evidence_id="zworkforce-stage-g-$(date -u +%Y%m%dT%H%M%SZ)-$$"
alert_json="$(python3 - "$evidence_id" <<'PY'
import datetime, json, sys
now=datetime.datetime.now(datetime.timezone.utc)
end=now+datetime.timedelta(minutes=5)
fmt=lambda d:d.isoformat().replace('+00:00','Z')
print(json.dumps([{
  "labels": {"alertname":"ZWorkforceReleaseEvidence","severity":"test","evidence_id":sys.argv[1]},
  "annotations":{"summary":"zWorkforce Stage G delivery verification"},
  "startsAt":fmt(now),
  "endsAt":fmt(end)
}]))
PY
)"

note "submitting synthetic alert through Alertmanager API"
alert_submitted_at="$(python3 -c 'import time; print(time.time())')"
printf '%s' "$alert_json" | ssh -o BatchMode=yes "$OBS_HOST" \
  "curl -fsS -X POST -H 'Content-Type: application/json' --data-binary @- http://127.0.0.1:${ALERTMANAGER_PORT}/api/v2/alerts >/dev/null" || \
  fail "Alertmanager rejected synthetic alert"

receiver_host="$(safe_host "$ALERT_RECEIVER_TEST_URL")"
note "waiting for external alert receipt from ${receiver_host} (URL redacted)"
receipt_ok=0
for _ in $(seq 1 12); do
  receipt="$(printf 'Authorization: Bearer %s\n' "$receiver_token" | curl -fsS -H @- --get "$ALERT_RECEIVER_TEST_URL" --data-urlencode "evidence_id=$evidence_id" 2>/dev/null || true)"
  if printf '%s' "$receipt" | python3 -c '
import datetime
import json
import re
import sys

record = json.load(sys.stdin)
expected_id = sys.argv[1]
submitted_at = float(sys.argv[2])
if not isinstance(record, dict) or record.get("evidence_id") != expected_id:
    raise SystemExit(1)
received_at = record.get("received_at")
if not isinstance(received_at, str):
    raise SystemExit(1)
received = datetime.datetime.fromisoformat(received_at.replace("Z", "+00:00"))
if received.tzinfo is None or received.timestamp() <= submitted_at:
    raise SystemExit(1)
alert_count = record.get("alert_count")
if isinstance(alert_count, bool) or not isinstance(alert_count, int) or alert_count < 1:
    raise SystemExit(1)
payload_hash = record.get("payload_sha256")
if not isinstance(payload_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", payload_hash):
    raise SystemExit(1)
' "$evidence_id" "$alert_submitted_at"; then
    receipt_ok=1
    break
  fi
  sleep 5
done
[[ "$receipt_ok" -eq 1 ]] || fail "no external receipt observed for Alertmanager-routed test alert"
note "Alertmanager delivery receipt verified"

trace_id="$(python3 - <<'PY'
import secrets
print(secrets.token_hex(16))
PY
)"
span_id="$(python3 - <<'PY'
import secrets
print(secrets.token_hex(8))
PY
)"
now_ns="$(python3 - <<'PY'
import time
print(time.time_ns())
PY
)"
end_ns="$((now_ns + 1000000))"
trace_json="$(python3 - "$trace_id" "$span_id" "$now_ns" "$end_ns" <<'PY'
import json, sys
print(json.dumps({"resourceSpans":[{"resource":{"attributes":[{"key":"service.name","value":{"stringValue":"zworkforce-release-evidence"}}]},"scopeSpans":[{"scope":{"name":"stage-g-verifier"},"spans":[{"traceId":sys.argv[1],"spanId":sys.argv[2],"name":"stage-g-synthetic-trace","kind":1,"startTimeUnixNano":sys.argv[3],"endTimeUnixNano":sys.argv[4]}]}]}]}))
PY
)"

note "submitting synthetic OTLP trace"
printf '%s' "$trace_json" | ssh -o BatchMode=yes "$OBS_HOST" \
  "curl -fsS -X POST -H 'Content-Type: application/json' --data-binary @- http://127.0.0.1:4318/v1/traces >/dev/null" || \
  fail "OTel Collector rejected synthetic trace"

trace_seen=0
for _ in $(seq 1 12); do
  if collector_logs 2>/dev/null | grep -F "$trace_id" >/dev/null; then
    trace_seen=1
    break
  fi
  sleep 1
done
[[ "$trace_seen" -eq 1 ]] || fail "OTel Collector logs did not contain the submitted synthetic trace ID"
note "OTLP trace receipt verified by exact trace ID in collector logs"

note "observability verification complete"
echo "VERIFY-OBS: PASS"
