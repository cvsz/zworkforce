#!/usr/bin/env bash
set -euo pipefail

# Render runtime-specific observability configuration before Docker Compose mounts it.
# Secrets are written only to ignored/generated local files and are never echoed.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
: "${ZWORKFORCE_VM_A_HOSTPORT:?set ZWORKFORCE_VM_A_HOSTPORT}"
: "${ZWORKFORCE_VM_B_HOSTPORT:?set ZWORKFORCE_VM_B_HOSTPORT}"
: "${ZWORKFORCE_METRICS_BEARER:?set ZWORKFORCE_METRICS_BEARER}"
: "${ALERTMANAGER_WEBHOOK_URL:?set ALERTMANAGER_WEBHOOK_URL}"

export ZWORKFORCE_VM_A_HOSTPORT ZWORKFORCE_VM_B_HOSTPORT ZWORKFORCE_METRICS_BEARER ALERTMANAGER_WEBHOOK_URL

python3 - "$DIR" <<'PY'
import json, os, pathlib, sys

root = pathlib.Path(sys.argv[1])

def q(value: str) -> str:
    # JSON strings are valid YAML scalars and safely escape credentials/URLs.
    return json.dumps(value)

prom = f'''global:
  scrape_interval: 15s
  evaluation_interval: 15s
rule_files:
  - /etc/prometheus/alert-rules.yml
alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]
scrape_configs:
  - job_name: "zworkforce-vm-a"
    metrics_path: "/metrics"
    scheme: "http"
    static_configs:
      - targets: [{q(os.environ["ZWORKFORCE_VM_A_HOSTPORT"])}]
    bearer_token: {q(os.environ["ZWORKFORCE_METRICS_BEARER"])}
  - job_name: "zworkforce-vm-b"
    metrics_path: "/metrics"
    scheme: "http"
    static_configs:
      - targets: [{q(os.environ["ZWORKFORCE_VM_B_HOSTPORT"])}]
    bearer_token: {q(os.environ["ZWORKFORCE_METRICS_BEARER"])}
  - job_name: "otel-collector"
    static_configs:
      - targets: ["otel-collector:8889"]
'''

alert = f'''route:
  group_by: ["alertname", "evidence_id"]
  group_wait: 1s
  group_interval: 10s
  repeat_interval: 1h
  receiver: operator
receivers:
  - name: operator
    webhook_configs:
      - url: {q(os.environ["ALERTMANAGER_WEBHOOK_URL"])}
        send_resolved: true
'''

for name, content in (("prometheus.rendered.yml", prom), ("alertmanager.rendered.yml", alert)):
    path = root / name
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)
PY

printf 'Rendered Prometheus and Alertmanager configuration without printing secret values.\n'
