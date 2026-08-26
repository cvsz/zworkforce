#!/usr/bin/env bash
set -Eeuo pipefail

# zWorkforce v3.0.4 External Gate Automation
#
# Automates:
#   F - Supabase S3-compatible storage verification (+ optional Qdrant)
#   E - Multi-replica HA deployment/verification (remote hosts required for external evidence)
#   G - Observability deployment/verification (OTel Collector + Prometheus + Alertmanager)
#   H - Windows trusted-signing/build/install verification (remote Windows host supported)
#
# IMPORTANT:
# - This script does NOT tag/publish v3.0.4.
# - It does NOT fabricate PASS.
# - Local-only HA/observability deployments are marked LOCAL, not external evidence.
# - Secrets are read from environment/.env.release and never printed.
#
# Canonical repo:
#   /home/cvsz/zworkforce
#
# Usage:
#   ./close-zworkforce-external-gates.sh verify
#   ./close-zworkforce-external-gates.sh F
#   ./close-zworkforce-external-gates.sh E
#   ./close-zworkforce-external-gates.sh G
#   ./close-zworkforce-external-gates.sh H
#   ./close-zworkforce-external-gates.sh all
#
# Optional config:
#   /home/cvsz/zworkforce/.env.release
#   HA_COMPOSE_FILE_A / HA_COMPOSE_FILE_B: remote Compose filenames
#   HA_EXPECTED_IMAGE / HA_EXPECTED_IMAGE_DIGEST: exact candidate image and OCI digest
#
# See generated .env.release.example.

REPO_DIR="${REPO_DIR:-/home/cvsz/zworkforce}"
ENV_FILE="${ENV_FILE:-$REPO_DIR/.env.release}"
STATE_DIR="${STATE_DIR:-$REPO_DIR/.release-evidence-state}"
LOG_DIR="${LOG_DIR:-$REPO_DIR/.release-evidence-logs}"
# Default to the exact repository candidate currently being verified. Operators
# may override this for a historical evidence replay, but must do so
# explicitly rather than silently collecting evidence against an old commit.
FROZEN_CANDIDATE="${FROZEN_CANDIDATE:-}"

mkdir -p "$STATE_DIR" "$LOG_DIR"

die(){ echo "ERROR: $*" >&2; exit 1; }
note(){ echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }
need(){ command -v "$1" >/dev/null 2>&1 || die "missing command: $1"; }

load_env(){
  [[ -f "$ENV_FILE" ]] || return 0
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
}

secret_present(){
  local n="$1"
  [[ -n "${!n:-}" ]]
}

sha256_file(){
  sha256sum "$1" | awk '{print $1}'
}

verify_candidate(){
  need git
  [[ -d "$REPO_DIR/.git" ]] || die "not a git repo: $REPO_DIR"

  local remote remote_lc main_sha
  remote="$(git -C "$REPO_DIR" remote get-url origin)"
  remote_lc="$(printf '%s' "$remote" | tr '[:upper:]' '[:lower:]')"
  [[ "$remote_lc" == *"github.com/cvsz/zworkforce"* ]] || \
    die "unexpected origin: $remote"

  git -C "$REPO_DIR" fetch --quiet --prune origin main
  main_sha="$(git -C "$REPO_DIR" rev-parse refs/remotes/origin/main)"

  if [[ -z "$FROZEN_CANDIDATE" ]]; then
    FROZEN_CANDIDATE="$main_sha"
    note "no FROZEN_CANDIDATE supplied; freezing fetched origin/main"
  fi

  note "origin/main=$main_sha"
  note "expected=$FROZEN_CANDIDATE"

  git -C "$REPO_DIR" cat-file -e "$FROZEN_CANDIDATE^{commit}" || \
    die "candidate commit not reachable"

  git -C "$REPO_DIR" merge-base --is-ancestor "$FROZEN_CANDIDATE" "$main_sha" || \
    die "candidate drift; origin/main no longer contains the frozen candidate (stop SHA-bound evidence collection)"

  if [[ "$main_sha" == "$FROZEN_CANDIDATE" ]]; then
    note "candidate verification PASS"
  else
    note "candidate verification PASS (frozen candidate is an ancestor of origin/main; forward work merged after freeze)"
  fi
}

mark(){
  local s="$1" status="$2" detail="${3:-}"
  printf '%s candidate=%s status=%s %s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "$FROZEN_CANDIDATE" "$status" "$detail" \
    > "$STATE_DIR/$s.status"
}

CURRENT_GATE=""
trap 'rc=$?; if [[ $rc -ne 0 && -n "$CURRENT_GATE" ]]; then mark "$CURRENT_GATE" FAIL gate_execution_failed; fi' EXIT

# ---------------------------------------------------------------------------
# Stage F — Supabase Storage / optional Qdrant
# ---------------------------------------------------------------------------

stage_f(){
  load_env
  verify_candidate
  need python3

  : "${SUPABASE_S3_ENDPOINT:?set SUPABASE_S3_ENDPOINT}"
  : "${SUPABASE_S3_BUCKET:?set SUPABASE_S3_BUCKET}"
  : "${SUPABASE_S3_REGION:?set SUPABASE_S3_REGION}"
  : "${SUPABASE_S3_ACCESS_KEY:?set SUPABASE_S3_ACCESS_KEY}"
  : "${SUPABASE_S3_SECRET_KEY:?set SUPABASE_S3_SECRET_KEY}"

  local stamp work payload key_a key_b
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  work="$LOG_DIR/$stamp-stage-F"
  mkdir -p "$work"

  payload="$work/artifact.txt"
  printf 'zworkforce-stage-f-%s\n' "$stamp" > "$payload"
  local expected_sha expected_size
  expected_sha="$(sha256_file "$payload")"
  expected_size="$(wc -c < "$payload" | tr -d ' ')"

  key_a="tenant-a/evidence/$expected_sha.txt"
  key_b="tenant-b/evidence/$expected_sha.txt"

  note "Stage F: testing Supabase S3-compatible storage"
  STAGE_F_PAYLOAD="$payload" \
  STAGE_F_KEY_A="$key_a" \
  STAGE_F_KEY_B="$key_b" \
  STAGE_F_EXPECTED_SHA="$expected_sha" \
  STAGE_F_EXPECTED_SIZE="$expected_size" \
  python3 - <<'PY'
import hashlib, os, sys, json

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError, BotoCoreError
except Exception as e:
    print("ERROR: boto3/botocore required:", e, file=sys.stderr)
    sys.exit(2)

endpoint=os.environ["SUPABASE_S3_ENDPOINT"]
bucket=os.environ["SUPABASE_S3_BUCKET"]
region=os.environ["SUPABASE_S3_REGION"]
access=os.environ["SUPABASE_S3_ACCESS_KEY"]
secret=os.environ["SUPABASE_S3_SECRET_KEY"]
payload=os.environ["STAGE_F_PAYLOAD"]
key_a=os.environ["STAGE_F_KEY_A"]
key_b=os.environ["STAGE_F_KEY_B"]
expected_sha=os.environ["STAGE_F_EXPECTED_SHA"]
expected_size=int(os.environ["STAGE_F_EXPECTED_SIZE"])

s3=boto3.client(
    "s3",
    endpoint_url=endpoint,
    region_name=region,
    aws_access_key_id=access,
    aws_secret_access_key=secret,
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
        connect_timeout=10,
        read_timeout=30,
        retries={"max_attempts": 2, "mode": "standard"},
    ),
)

data=open(payload,"rb").read()
try:
    s3.put_object(Bucket=bucket, Key=key_a, Body=data, ContentType="text/plain",
                  Metadata={"sha256": expected_sha, "tenant":"tenant-a"})
except ClientError as exc:
    response=exc.response or {}
    error=response.get("Error") or {}
    metadata=response.get("ResponseMetadata") or {}
    print(
        "S3 operation=PutObject failed "
        f"code={error.get('Code') or 'unknown'} "
        f"status={metadata.get('HTTPStatusCode') or 'unknown'}",
        file=sys.stderr,
    )
    sys.exit(1)
except BotoCoreError as exc:
    print(f"S3 operation=PutObject failed client={type(exc).__name__}", file=sys.stderr)
    sys.exit(1)

obj=s3.get_object(Bucket=bucket, Key=key_a)
got=obj["Body"].read()
got_sha=hashlib.sha256(got).hexdigest()

assert got_sha == expected_sha, (got_sha, expected_sha)
assert len(got) == expected_size, (len(got), expected_size)
assert obj.get("ContentType") == "text/plain"

# Nonexistent object must fail.
try:
    s3.get_object(Bucket=bucket, Key=key_b)
except ClientError as e:
    response=e.response or {}
    code=str((response.get("Error") or {}).get("Code", ""))
    # Supabase can return a status-only error for a missing object, with an
    # empty S3 error code. Accept the documented missing/denied status while
    # still rejecting unrelated errors.
    missing_object_status=(response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
    if code not in ("NoSuchKey", "404", "AccessDenied") and missing_object_status not in (403, 404):
        raise
else:
    raise AssertionError("tenant-b/nonexistent object unexpectedly readable")

# Signed URL generation is validated without printing the URL.
url=s3.generate_presigned_url(
    "get_object",
    Params={"Bucket":bucket,"Key":key_a},
    ExpiresIn=60,
)
assert isinstance(url,str) and len(url)>20

# Delete and verify absence.
s3.delete_object(Bucket=bucket, Key=key_a)
try:
    s3.get_object(Bucket=bucket, Key=key_a)
except ClientError:
    pass
else:
    raise AssertionError("deleted object still readable")

print(json.dumps({
  "storage":"PASS",
  "sha256":expected_sha,
  "bytes":expected_size,
  "mime":"text/plain",
  "presigned_url_generated":True,
  "delete_verified":True
}))
PY

  # Optional real Qdrant evidence
  if [[ -n "${QDRANT_URL:-}" ]]; then
    note "Stage F: Qdrant configured; running tenant-isolation smoke"
    QDRANT_URL="${QDRANT_URL}" QDRANT_API_KEY="${QDRANT_API_KEY:-}" python3 - <<'PY'
import os, sys, uuid
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
except Exception as e:
    print("ERROR: qdrant-client required:", e, file=sys.stderr)
    sys.exit(2)

url=os.environ["QDRANT_URL"]
api_key=os.environ.get("QDRANT_API_KEY") or None
client=QdrantClient(url=url, api_key=api_key, timeout=20)

collection="zworkforce_release_evidence"
try:
    client.delete_collection(collection)
except Exception:
    pass
client.create_collection(collection, vectors_config=VectorParams(size=4, distance=Distance.COSINE))

pid=str(uuid.uuid4())
client.upsert(collection, [
    PointStruct(id=pid, vector=[1.0,0.0,0.0,0.0], payload={"tenant_id":"tenant-a"})
])

a=client.query_points(
    collection_name=collection,
    query=[1.0,0.0,0.0,0.0],
    query_filter=Filter(must=[FieldCondition(key="tenant_id",match=MatchValue(value="tenant-a"))]),
    limit=5
).points
b=client.query_points(
    collection_name=collection,
    query=[1.0,0.0,0.0,0.0],
    query_filter=Filter(must=[FieldCondition(key="tenant_id",match=MatchValue(value="tenant-b"))]),
    limit=5
).points

assert len(a) >= 1
assert len(b) == 0
client.delete_collection(collection)
print("qdrant_tenant_isolation=PASS")
PY
  else
    note "Stage F: QDRANT_URL not set; vector evidence remains optional/pending per release config"
  fi

  mark F PASS "supabase_s3_verified"
  note "STAGE F VERDICT: PASS"
}

# ---------------------------------------------------------------------------
# Stage E — External multi-replica HA
# ---------------------------------------------------------------------------

stage_e(){
  load_env
  verify_candidate
  need ssh

  : "${HA_HOST_A:?set HA_HOST_A (ssh target)}"
  : "${HA_HOST_B:?set HA_HOST_B (ssh target)}"
  : "${HA_DEPLOY_DIR:?set HA_DEPLOY_DIR on remote hosts}"
  : "${HA_DB_DSN_SECRET_REF:?set HA_DB_DSN_SECRET_REF (reference name only)}"
  : "${HA_EXPECTED_IMAGE:?set HA_EXPECTED_IMAGE to the exact candidate image reference}"
  : "${HA_EXPECTED_IMAGE_DIGEST:?set HA_EXPECTED_IMAGE_DIGEST to the exact candidate OCI digest}"

  local compose_a="${HA_COMPOSE_FILE_A:-compose.vm-a.yaml}"
  local compose_b="${HA_COMPOSE_FILE_B:-compose.vm-b.yaml}"

  [[ "$HA_HOST_A" != "$HA_HOST_B" ]] || die "HA_HOST_A and HA_HOST_B must differ"

  note "Stage E: verifying two distinct external hosts are reachable"
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$HA_HOST_A" 'hostname && uptime'
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$HA_HOST_B" 'hostname && uptime'

  # We intentionally do NOT inject DB secrets via shell.
  # Each host must already have its external secret/config material provisioned.
  note "Stage E: deploying/starting zworkforce HA services on host A"
  ssh "$HA_HOST_A" "cd '$HA_DEPLOY_DIR' && test -f '$compose_a' && ZWORKFORCE_IMAGE='$HA_EXPECTED_IMAGE' ZWORKFORCE_INSTANCE_ID=vm-a docker compose -f '$compose_a' pull && ZWORKFORCE_IMAGE='$HA_EXPECTED_IMAGE' ZWORKFORCE_INSTANCE_ID=vm-a docker compose -f '$compose_a' up -d"

  note "Stage E: deploying/starting zworkforce HA services on host B"
  ssh "$HA_HOST_B" "cd '$HA_DEPLOY_DIR' && test -f '$compose_b' && ZWORKFORCE_IMAGE='$HA_EXPECTED_IMAGE' ZWORKFORCE_INSTANCE_ID=vm-b docker compose -f '$compose_b' pull && ZWORKFORCE_IMAGE='$HA_EXPECTED_IMAGE' ZWORKFORCE_INSTANCE_ID=vm-b docker compose -f '$compose_b' up -d"

  note "Stage E: capturing replica identities"
  local a_ids b_ids
  a_ids="$(ssh "$HA_HOST_A" "cd '$HA_DEPLOY_DIR' && docker compose -f '$compose_a' ps --format json" | sha256sum | awk '{print $1}')"
  b_ids="$(ssh "$HA_HOST_B" "cd '$HA_DEPLOY_DIR' && docker compose -f '$compose_b' ps --format json" | sha256sum | awk '{print $1}')"
  note "hostA_replica_snapshot_sha256=$a_ids"
  note "hostB_replica_snapshot_sha256=$b_ids"

  # HA verification is delegated to repository's own release drill if present.
  if [[ -x "$REPO_DIR/scripts/release/verify-ha.sh" ]]; then
    HA_HOST_A="$HA_HOST_A" HA_HOST_B="$HA_HOST_B" HA_DEPLOY_DIR="$HA_DEPLOY_DIR" \
      HA_COMPOSE_FILE_A="$compose_a" HA_COMPOSE_FILE_B="$compose_b" \
      HA_EXPECTED_IMAGE="$HA_EXPECTED_IMAGE" HA_EXPECTED_IMAGE_DIGEST="$HA_EXPECTED_IMAGE_DIGEST" \
      "$REPO_DIR/scripts/release/verify-ha.sh"
  elif [[ -x "$REPO_DIR/scripts/verify-ha.sh" ]]; then
    HA_HOST_A="$HA_HOST_A" HA_HOST_B="$HA_HOST_B" HA_DEPLOY_DIR="$HA_DEPLOY_DIR" \
      HA_COMPOSE_FILE_A="$compose_a" HA_COMPOSE_FILE_B="$compose_b" \
      HA_EXPECTED_IMAGE="$HA_EXPECTED_IMAGE" HA_EXPECTED_IMAGE_DIGEST="$HA_EXPECTED_IMAGE_DIGEST" \
      "$REPO_DIR/scripts/verify-ha.sh"
  else
    die "no repository HA verification script found; cannot honestly mark Stage E PASS"
  fi

  mark E PASS "external_multi_replica_verified"
  note "STAGE E VERDICT: PASS"
}

# ---------------------------------------------------------------------------
# Stage G — Observability deployment + verification
# ---------------------------------------------------------------------------

write_observability_compose(){
  local out="$1"
  cat > "$out" <<'YAML'
secrets:
  metrics-bearer:
    file: ./metrics-bearer
  alertmanager-webhook-url:
    file: ./alertmanager-webhook-url

services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.135.0
    command: ["--config=/etc/otelcol/config.yaml"]
    volumes:
      - ./otel-collector.yaml:/etc/otelcol/config.yaml:ro
    ports:
      - "4317:4317"
      - "4318:4318"
      - "8889:8889"
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:v3.5.0
    command: ["--config.file=/etc/prometheus/prometheus.yml"]
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./alert-rules.yml:/etc/prometheus/alert-rules.yml:ro
    secrets:
      - source: metrics-bearer
        target: metrics-bearer
    group_add:
      - "${OBS_SECRET_GID:?set OBS_SECRET_GID}"
    ports:
      - "9090:9090"
    restart: unless-stopped

  alertmanager:
    image: prom/alertmanager:v0.28.1
    command: ["--config.file=/etc/alertmanager/alertmanager.yml"]
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
    secrets:
      - source: alertmanager-webhook-url
        target: alertmanager-webhook-url
    group_add:
      - "${OBS_SECRET_GID:?set OBS_SECRET_GID}"
    ports:
      - "9093:9093"
    restart: unless-stopped
YAML
}

metrics_hostport_for(){
  local explicit="$1" ssh_target="$2"
  if [[ -n "$explicit" ]]; then
    printf '%s' "$explicit"
    return
  fi

  ssh_target="${ssh_target#*@}"
  if [[ "$ssh_target" == *:* ]]; then
    printf '%s' "$ssh_target"
  else
    printf '%s:%s' "$ssh_target" "${ZWORKFORCE_METRICS_PORT:-9456}"
  fi
}

stage_g(){
  load_env
  verify_candidate
  need ssh
  need curl

  : "${OBS_HOST:?set OBS_HOST (ssh target)}"
  : "${OBS_DEPLOY_DIR:?set OBS_DEPLOY_DIR}"
  : "${HA_HOST_A:?set HA_HOST_A (VM-A SSH target)}"
  : "${HA_HOST_B:?set HA_HOST_B (VM-B SSH target)}"
  : "${ZWORKFORCE_METRICS_URL:?set ZWORKFORCE_METRICS_URL}"
  : "${ZWORKFORCE_HEALTH_URL:?set ZWORKFORCE_HEALTH_URL}"
  : "${ZWORKFORCE_READY_URL:?set ZWORKFORCE_READY_URL}"
  : "${ALERT_RECEIVER_TEST_URL:?set ALERT_RECEIVER_TEST_URL or external receipt endpoint}"
  : "${ALERTMANAGER_WEBHOOK_URL:?set ALERTMANAGER_WEBHOOK_URL}"
  : "${ZWORKFORCE_METRICS_BEARER:?set ZWORKFORCE_METRICS_BEARER}"

  local metrics_a metrics_b
  metrics_a="$(metrics_hostport_for "${ZWORKFORCE_METRICS_HOSTPORT_A:-${ZWORKFORCE_METRICS_HOSTPORT:-}}" "$HA_HOST_A")"
  metrics_b="$(metrics_hostport_for "${ZWORKFORCE_METRICS_HOSTPORT_B:-}" "$HA_HOST_B")"

  local tmp="$LOG_DIR/obs-deploy-$(date -u +%Y%m%dT%H%M%SZ)"
  umask 077
  mkdir -p "$tmp"
  write_observability_compose "$tmp/compose.yml"
  printf '%s' "$ZWORKFORCE_METRICS_BEARER" > "$tmp/metrics-bearer"
  printf '%s' "$ALERTMANAGER_WEBHOOK_URL" > "$tmp/alertmanager-webhook-url"

  cat > "$tmp/otel-collector.yaml" <<'YAML'
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
exporters:
  debug:
    verbosity: basic
  prometheus:
    endpoint: 0.0.0.0:8889
service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [debug]
    metrics:
      receivers: [otlp]
      exporters: [prometheus, debug]
YAML

  cat > "$tmp/prometheus.yml" <<YAML
global:
  scrape_interval: 15s
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
    authorization:
      type: Bearer
      credentials_file: "/run/secrets/metrics-bearer"
    static_configs:
      - targets: ["$metrics_a"]
  - job_name: "zworkforce-vm-b"
    metrics_path: "/metrics"
    scheme: "http"
    authorization:
      type: Bearer
      credentials_file: "/run/secrets/metrics-bearer"
    static_configs:
      - targets: ["$metrics_b"]
  - job_name: "otel-collector"
    static_configs:
      - targets: ["otel-collector:8889"]
YAML

  cat > "$tmp/alert-rules.yml" <<'YAML'
groups:
  - name: zworkforce-release-evidence
    rules:
      - alert: ZWorkforceEvidenceHeartbeatMissing
        expr: up{job=~"zworkforce-vm-(a|b)"} == 0
        for: 30s
        labels:
          severity: test
        annotations:
          summary: "zWorkforce release evidence test alert"
YAML

  cat > "$tmp/alertmanager.yml" <<YAML
route:
  receiver: operator
receivers:
  - name: operator
    webhook_configs:
      - url_file: "/run/secrets/alertmanager-webhook-url"
        send_resolved: true
YAML

  note "Stage G: copying observability config to $OBS_HOST"
  ssh "$OBS_HOST" "mkdir -p '$OBS_DEPLOY_DIR'"
  scp -q "$tmp/"* "$OBS_HOST:$OBS_DEPLOY_DIR/"
  ssh "$OBS_HOST" "chmod 640 '$OBS_DEPLOY_DIR/metrics-bearer' '$OBS_DEPLOY_DIR/alertmanager-webhook-url'"

  local secret_gid
  secret_gid="$(ssh "$OBS_HOST" "stat -c '%g' '$OBS_DEPLOY_DIR/metrics-bearer'")"
  [[ "$secret_gid" =~ ^[0-9]+$ ]] || die "observability secret group id is invalid"

  note "Stage G: deploying OTel/Prometheus/Alertmanager"
  ssh "$OBS_HOST" "cd '$OBS_DEPLOY_DIR' && OBS_SECRET_GID='$secret_gid' docker compose -f compose.yml up -d"
  ssh "$OBS_HOST" "docker exec zworkforce-observability-prometheus-1 sh -c 'kill -HUP 1' || true"

  note "Stage G: health/readiness"
  curl -fsS "$ZWORKFORCE_HEALTH_URL" >/dev/null
  curl -fsS "$ZWORKFORCE_READY_URL" >/dev/null

 # Metrics auth can use an existing locally exported token without printing it.
 if [[ -n "${ZWORKFORCE_METRICS_BEARER:-}" ]]; then
    printf '%s\n' "Authorization: Bearer $ZWORKFORCE_METRICS_BEARER" |
      curl -fsS -H @- "$ZWORKFORCE_METRICS_URL" \
     | grep -E 'zworkforce_|provider_|queue_' >/dev/null
 else
    die "ZWORKFORCE_METRICS_BEARER required for authenticated metrics evidence"
  fi

  # Verify Prometheus and Alertmanager HTTP APIs on remote host.
  ssh "$OBS_HOST" "curl -fsS http://127.0.0.1:9090/-/ready >/dev/null"
  ssh "$OBS_HOST" "curl -fsS http://127.0.0.1:9093/-/ready >/dev/null"

  # Optional repository-specific trace/alert evidence drill.
  if [[ -x "$REPO_DIR/scripts/release/verify-observability.sh" ]]; then
    ALERTMANAGER_PORT=9093 OBS_COMPOSE_FILE=compose.yml "$REPO_DIR/scripts/release/verify-observability.sh"
  elif [[ -x "$REPO_DIR/scripts/verify-observability.sh" ]]; then
    ALERTMANAGER_PORT=9093 OBS_COMPOSE_FILE=compose.yml "$REPO_DIR/scripts/verify-observability.sh"
  else
    die "no repository observability verification script found; cannot prove trace + actual alert delivery"
  fi

  mark G PASS "external_observability_verified"
  note "STAGE G VERDICT: PASS"
}

# ---------------------------------------------------------------------------
# Stage H — Windows trusted signing
# ---------------------------------------------------------------------------

ps_single_quote(){
  local value="${1:-}"
  value="${value//\'/\'\'}"
  printf "'%s'" "$value"
}

run_remote_pwsh(){
  local script="$1"
  printf '%s\n' '$ErrorActionPreference = "Stop"' "$script" | \
    ssh "$WINDOWS_HOST" 'pwsh -NoProfile -NonInteractive -Command -'
}

stage_h(){
  load_env
  verify_candidate
  need ssh
  need python3

  : "${WINDOWS_HOST:?set WINDOWS_HOST (OpenSSH-enabled Windows target)}"
  : "${WINDOWS_REPO_DIR:?set WINDOWS_REPO_DIR e.g. C:/src/zworkforce}"
  : "${WINDOWS_MSIX_PFX_PATH:?set WINDOWS_MSIX_PFX_PATH on Windows host}"
  : "${WINDOWS_MSIX_PFX_PASSWORD:?set WINDOWS_MSIX_PFX_PASSWORD in secure env}"
  : "${WINDOWS_MSIX_PUBLISHER:?set WINDOWS_MSIX_PUBLISHER}"
  : "${ZWORKFORCE_HTTPS_ENDPOINT:?set ZWORKFORCE_HTTPS_ENDPOINT}"

  local release_version
  release_version="$(PYTHONPATH="$REPO_DIR" python3 -c 'from zworkforce import __version__; print(__version__)')"

  # Never copy/export PFX material from this script. It must already be securely
  # provisioned on the Windows host.
  note "Stage H: verifying Windows host"
  run_remote_pwsh '$PSVersionTable.PSVersion.ToString()'

  note "Stage H: build/test/sign package"
  local ps_repo_dir ps_pfx_path ps_pfx_password ps_publisher
  ps_repo_dir="$(ps_single_quote "$WINDOWS_REPO_DIR")"
  ps_pfx_path="$(ps_single_quote "$WINDOWS_MSIX_PFX_PATH")"
  ps_pfx_password="$(ps_single_quote "$WINDOWS_MSIX_PFX_PASSWORD")"
  ps_publisher="$(ps_single_quote "$WINDOWS_MSIX_PUBLISHER")"

  local candidate_script ps_candidate
  ps_candidate="$(ps_single_quote "$FROZEN_CANDIDATE")"
  candidate_script="$(printf '%s\n' \
    "Set-Location $ps_repo_dir" \
    '$sha = (git rev-parse HEAD).Trim()' \
    "if (\$sha -ne $ps_candidate) { [Console]::Error.WriteLine(\"Windows checkout does not match candidate $FROZEN_CANDIDATE\"); exit 1 }" \
    'Write-Output ("WINDOWS_CANDIDATE=" + $sha)')"
  run_remote_pwsh "$candidate_script"

  local build_script
  build_script="$(printf '%s\n' \
    "Set-Location $ps_repo_dir" \
    "\$env:ZWORKFORCE_MSIX_SIGNING_PFX_PATH = $ps_pfx_path" \
    "\$env:ZWORKFORCE_MSIX_SIGNING_PFX_PASSWORD = $ps_pfx_password" \
    "\$env:ZWORKFORCE_MSIX_SIGNING_PUBLISHER = $ps_publisher" \
    "\$env:ZWORKFORCE_MSIX_REQUIRE_TRUSTED_SIGNING = 'true'" \
    "& ./ZWorkforceClient/build/windows/Build-Client.ps1 -Configuration Release -Platform x64; if (-not \$?) { exit 1 }" \
    "& ./ZWorkforceClient/build/windows/Test-Client.ps1 -Configuration Release; if (-not \$?) { exit 1 }" \
    "& ./ZWorkforceClient/build/windows/Package-Client.ps1 -Configuration Release -Platform x64 -Version '$release_version'; if (-not \$?) { exit 1 }" \
    "& ./ZWorkforceClient/build/windows/Test-Client.ps1 -Configuration Release -ExpectedVersion '$release_version.0' -LaunchSmoke; if (-not \$?) { exit 1 }")"
  run_remote_pwsh "$build_script"

  # Find newest MSIX/MSIXBundle and validate Authenticode + hash without
  # printing signing secrets.
  local inspect_script
  inspect_script="$(printf '%s\n' \
    "Set-Location $ps_repo_dir" \
    '$packages = @(Get-ChildItem -Recurse -File | Where-Object { $_.Extension -in @(".msix", ".msixbundle") } | Sort-Object LastWriteTime -Descending)' \
    'if ($packages.Count -eq 0) { [Console]::Error.WriteLine("MSIX/MSIXBundle not found"); exit 1 }' \
    '$pkg = $packages[0]' \
    '$sig = Get-AuthenticodeSignature $pkg.FullName' \
    'if ($sig.Status -ne "Valid") { [Console]::Error.WriteLine("Signature invalid: " + $sig.Status); exit 1 }' \
    '$hash = (Get-FileHash -Algorithm SHA256 $pkg.FullName).Hash' \
    'Write-Output ("PACKAGE=" + $pkg.Name)' \
    'Write-Output ("SHA256=" + $hash)' \
    'Write-Output ("PUBLISHER=" + $sig.SignerCertificate.Subject)' \
    'Write-Output ("SIGNATURE=" + $sig.Status)')"
  run_remote_pwsh "$inspect_script"

  # Live HTTPS endpoint check from Windows host. The helper already returns a
  # complete PowerShell single-quoted literal; do not add a second quote pair.
  local ps_health_endpoint
  ps_health_endpoint="$(ps_single_quote "$ZWORKFORCE_HTTPS_ENDPOINT/health")"
  run_remote_pwsh "Invoke-WebRequest -UseBasicParsing $ps_health_endpoint | Out-Null; if (-not \$?) { exit 1 }"

  if [[ -x "$REPO_DIR/scripts/release/verify-windows-live.sh" ]]; then
    WINDOWS_HOST="$WINDOWS_HOST" \
      ZWORKFORCE_HTTPS_ENDPOINT="$ZWORKFORCE_HTTPS_ENDPOINT" \
      "$REPO_DIR/scripts/release/verify-windows-live.sh"
  fi

  mark H PASS "trusted_windows_signing_verified"
  note "STAGE H VERDICT: PASS"
}

status(){
  verify_candidate
  for s in F E G H; do
    if [[ -f "$STATE_DIR/$s.status" ]]; then
      local line
      line="$(cat "$STATE_DIR/$s.status")"
      if [[ "$line" == *"candidate=$FROZEN_CANDIDATE "* ]]; then
        echo "$s: $line"
      else
        echo "$s: STALE_EVIDENCE candidate-mismatch rerun-stage-$s"
      fi
    else
      echo "$s: NOT VERIFIED"
    fi
  done
}

case "${1:-}" in
  verify)
    load_env
    verify_candidate
    ;;
  status)
    load_env
    status
    ;;
  F)
    CURRENT_GATE=F
    stage_f
    CURRENT_GATE=
    ;;
  E)
    CURRENT_GATE=E
    stage_e
    CURRENT_GATE=
    ;;
  G)
    CURRENT_GATE=G
    stage_g
    CURRENT_GATE=
    ;;
  H)
    CURRENT_GATE=H
    stage_h
    CURRENT_GATE=
    ;;
  all)
    CURRENT_GATE=F
    stage_f
    CURRENT_GATE=E
    stage_e
    CURRENT_GATE=G
    stage_g
    CURRENT_GATE=H
    stage_h
    CURRENT_GATE=
    ;;
  *)
    cat <<'EOF'
Usage:
  close-zworkforce-external-gates.sh verify
  close-zworkforce-external-gates.sh status
  close-zworkforce-external-gates.sh F
  close-zworkforce-external-gates.sh E
  close-zworkforce-external-gates.sh G
  close-zworkforce-external-gates.sh H
  close-zworkforce-external-gates.sh all
EOF
    exit 2
    ;;
esac
