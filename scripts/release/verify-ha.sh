#!/usr/bin/env bash
set -euo pipefail

# zWorkforce v3.0.4 HA Runtime VM x2 release verification (Stage E)
# Fail-closed verifier: PASS requires real shared-DB lease/outbox evidence.

fail(){ echo "VERIFY-HA: FAIL: $*" >&2; exit 1; }
note(){ echo "VERIFY-HA: $*"; }

: "${HA_HOST_A:?set HA_HOST_A (ssh target)}"
: "${HA_HOST_B:?set HA_HOST_B (ssh target)}"
: "${HA_DEPLOY_DIR:?set HA_DEPLOY_DIR on remote hosts}"
: "${HA_COMPOSE_FILE_A:?set HA_COMPOSE_FILE_A on VM-A (for example compose.vm-a.yaml)}"
: "${HA_COMPOSE_FILE_B:?set HA_COMPOSE_FILE_B on VM-B (for example compose.vm-b.yaml)}"
: "${HA_EXPECTED_IMAGE:?set HA_EXPECTED_IMAGE to the exact candidate image reference}"
: "${HA_EXPECTED_IMAGE_DIGEST:?set HA_EXPECTED_IMAGE_DIGEST to the exact candidate OCI digest}"
HA_IMAGE_PULL_POLICY="${HA_IMAGE_PULL_POLICY:-always}"
HA_IMAGE_PROVENANCE_FILE="${HA_IMAGE_PROVENANCE_FILE:-candidate-image-provenance.env}"
HA_EXPECTED_IMAGE_PROVENANCE_SHA256="${HA_EXPECTED_IMAGE_PROVENANCE_SHA256:-}"
HA_EXPECTED_DB_PROJECT_REF="${HA_EXPECTED_DB_PROJECT_REF:-qhprcfdgajhmdzvnsffb}"
HA_EXPECTED_DB_HOST="${HA_EXPECTED_DB_HOST:-aws-0-ap-northeast-1.pooler.supabase.com}"
HA_EXPECTED_DB_PORT="${HA_EXPECTED_DB_PORT:-5432}"
[[ "$HA_HOST_A" != "$HA_HOST_B" ]] || fail "HA_HOST_A and HA_HOST_B must differ"
[[ "$HA_EXPECTED_IMAGE_DIGEST" =~ ^sha256:[0-9a-fA-F]{64}$ ]] || fail "HA_EXPECTED_IMAGE_DIGEST must be a sha256 OCI digest"
[[ "$HA_EXPECTED_DB_PROJECT_REF" =~ ^[a-z0-9]{20,40}$ ]] || fail "HA_EXPECTED_DB_PROJECT_REF is invalid"
[[ "$HA_EXPECTED_DB_HOST" =~ ^[a-z0-9.-]+$ ]] || fail "HA_EXPECTED_DB_HOST is invalid"
[[ "$HA_EXPECTED_DB_PORT" =~ ^[0-9]{1,5}$ ]] || fail "HA_EXPECTED_DB_PORT is invalid"
case "$HA_IMAGE_PULL_POLICY" in
  always) ;;
  never)
    [[ "$HA_EXPECTED_IMAGE_PROVENANCE_SHA256" =~ ^[0-9a-fA-F]{64}$ ]] || \
      fail "HA_EXPECTED_IMAGE_PROVENANCE_SHA256 is required for preloaded images"
    ;;
  *) fail "HA_IMAGE_PULL_POLICY must be always or never" ;;
esac

ssh_opts=(-o BatchMode=yes -o ConnectTimeout=10)

note "checking host reachability"
ssh "${ssh_opts[@]}" "$HA_HOST_A" hostname >/dev/null || fail "host A unreachable"
ssh "${ssh_opts[@]}" "$HA_HOST_B" hostname >/dev/null || fail "host B unreachable"

for label in A B; do
  if [[ "$label" == A ]]; then
    host="$HA_HOST_A"
    compose_file="$HA_COMPOSE_FILE_A"
  else
    host="$HA_HOST_B"
    compose_file="$HA_COMPOSE_FILE_B"
  fi
  services="$(ssh "${ssh_opts[@]}" "$host" "cd '$HA_DEPLOY_DIR' && docker compose -f '$compose_file' ps --services --filter status=running 2>/dev/null" || true)"
  for svc in serve worker scheduler outbox; do
    grep -qx "$svc" <<<"$services" || fail "host $label missing running service: $svc"
  done
  ssh "${ssh_opts[@]}" "$host" "curl -fsS http://127.0.0.1:9456/health >/dev/null" || fail "host $label API health failed"
done
note "both VMs have running serve+worker+scheduler+outbox services"

# Runtime identity must be explicit and distinct; container names are not authority.
a_instance="$(ssh "${ssh_opts[@]}" "$HA_HOST_A" "cd '$HA_DEPLOY_DIR' && docker compose -f '$HA_COMPOSE_FILE_A' exec -T serve sh -lc 'printf %s \"\${ZWORKFORCE_INSTANCE_ID:-}\"'" 2>/dev/null || true)"
b_instance="$(ssh "${ssh_opts[@]}" "$HA_HOST_B" "cd '$HA_DEPLOY_DIR' && docker compose -f '$HA_COMPOSE_FILE_B' exec -T serve sh -lc 'printf %s \"\${ZWORKFORCE_INSTANCE_ID:-}\"'" 2>/dev/null || true)"
[[ -n "$a_instance" ]] || fail "VM-A ZWORKFORCE_INSTANCE_ID is unset"
[[ -n "$b_instance" ]] || fail "VM-B ZWORKFORCE_INSTANCE_ID is unset"
[[ "$a_instance" != "$b_instance" ]] || fail "VM instance identities collide"
[[ "$a_instance" == "vm-a" ]] || fail "VM-A identity must be vm-a (got $a_instance)"
[[ "$b_instance" == "vm-b" ]] || fail "VM-B identity must be vm-b (got $b_instance)"
note "distinct runtime identities confirmed: $a_instance / $b_instance"

# Verify the configured DSN target without printing the DSN or its password.
# The username suffix identifies the Supabase project, while the session
# pooler host/port and TLS mode prevent an accidental transaction-pooler or
# wrong-project cutover from being reported as shared HA evidence.
verify_database_target(){
  local label="$1" host="$2" compose_file="$3" target_output
  target_output="$(ssh "${ssh_opts[@]}" "$host" \
    "cd '$HA_DEPLOY_DIR' && docker compose -f '$compose_file' exec -T serve python - '$HA_EXPECTED_DB_PROJECT_REF' '$HA_EXPECTED_DB_HOST' '$HA_EXPECTED_DB_PORT'" <<'PY'
import os
import sys
from urllib.parse import parse_qs, urlsplit

expected_project, expected_host, expected_port = sys.argv[1:]
dsn = os.environ.get("ZWORKFORCE_DATABASE_URL", "").strip()
if not dsn:
    raise SystemExit("database_target=FAIL missing_dsn")
try:
    parsed = urlsplit(dsn)
    port = parsed.port
except ValueError:
    raise SystemExit("database_target=FAIL malformed_dsn")
username = parsed.username or ""
project_ref = username.split(".", 1)[1] if "." in username else ""
sslmode = parse_qs(parsed.query).get("sslmode", [""])[0]
if project_ref != expected_project:
    raise SystemExit("database_target=FAIL wrong_project")
if parsed.hostname != expected_host:
    raise SystemExit("database_target=FAIL wrong_host")
if port != int(expected_port):
    raise SystemExit("database_target=FAIL wrong_port")
if sslmode != "require":
    raise SystemExit("database_target=FAIL tls_required")
print("database_target=PASS")
PY
  )" || fail "host $label PostgreSQL target metadata check failed"
  grep -Fxq "database_target=PASS" <<<"$target_output" || \
    fail "host $label is not configured for the expected qhpr session pooler"
  note "host $label PostgreSQL target verified (qhpr session pooler/TLS)"
}

verify_database_target A "$HA_HOST_A" "$HA_COMPOSE_FILE_A"
verify_database_target B "$HA_HOST_B" "$HA_COMPOSE_FILE_B"

# current_database/current_user are not project identifiers: two independent
# Supabase projects can return the same values. Prove that both replicas see a
# marker written through VM-A, then remove the marker before collecting lease
# evidence. The marker contains only the frozen candidate SHA.
shared_database_probe(){
  local probe_key
  probe_key="release_ha_probe_${FROZEN_CANDIDATE}_$(date -u +%Y%m%dT%H%M%SZ)"
  local probe_value="$FROZEN_CANDIDATE"
  local cleanup_cmd="cd '$HA_DEPLOY_DIR' && docker compose -f '$HA_COMPOSE_FILE_A' exec -T serve python - '$probe_key' '$probe_value'"

  ssh "${ssh_opts[@]}" "$HA_HOST_A" \
    "cd '$HA_DEPLOY_DIR' && docker compose -f '$HA_COMPOSE_FILE_A' exec -T serve python - '$probe_key' '$probe_value'" <<'PY' || \
    fail "VM-A could not write the shared PostgreSQL probe"
import os
import sys
import psycopg

key, value = sys.argv[1:3]
with psycopg.connect(os.environ["ZWORKFORCE_DATABASE_URL"], connect_timeout=5) as conn:
    conn.execute("INSERT INTO schema_meta(key,value) VALUES(%s,%s)", (key, value))
PY

  if ! ssh "${ssh_opts[@]}" "$HA_HOST_B" \
    "cd '$HA_DEPLOY_DIR' && docker compose -f '$HA_COMPOSE_FILE_B' exec -T serve python - '$probe_key' '$probe_value'" <<'PY'
import os
import sys
import psycopg

key, value = sys.argv[1:3]
with psycopg.connect(os.environ["ZWORKFORCE_DATABASE_URL"], connect_timeout=5) as conn:
    row = conn.execute("SELECT value FROM schema_meta WHERE key=%s", (key,)).fetchone()
    if row is None or row[0] != value:
        raise SystemExit("shared PostgreSQL probe marker was not visible on VM-B")
print("shared_database_probe=PASS")
PY
  then
    ssh "${ssh_opts[@]}" "$HA_HOST_A" "$cleanup_cmd" <<'PY' || true
import os
import sys
import psycopg

key, value = sys.argv[1:3]
with psycopg.connect(os.environ["ZWORKFORCE_DATABASE_URL"], connect_timeout=5) as conn:
    conn.execute("DELETE FROM schema_meta WHERE key=%s AND value=%s", (key, value))
PY
    fail "VM-A and VM-B do not share the same PostgreSQL database"
  fi

  ssh "${ssh_opts[@]}" "$HA_HOST_A" "$cleanup_cmd" <<'PY' || \
    fail "could not clean up the shared PostgreSQL probe marker"
import os
import sys
import psycopg

key, value = sys.argv[1:3]
with psycopg.connect(os.environ["ZWORKFORCE_DATABASE_URL"], connect_timeout=5) as conn:
    conn.execute("DELETE FROM schema_meta WHERE key=%s AND value=%s", (key, value))
PY
  note "shared PostgreSQL database probe passed and marker was removed"
}

shared_database_probe

# Verify the deployed Compose files resolve the exact candidate image and expose
# the runtime identity contract before querying shared state.
verify_host(){
  local label="$1" host="$2" compose_file="$3"
  ssh "${ssh_opts[@]}" "$host" "cd '$HA_DEPLOY_DIR' && test -f '$compose_file'" || \
    fail "host $label missing compose file: $compose_file"

  local resolved_images
  resolved_images="$(ssh "${ssh_opts[@]}" "$host" "cd '$HA_DEPLOY_DIR' && ZWORKFORCE_IMAGE='$HA_EXPECTED_IMAGE' docker compose -f '$compose_file' config --images")" || \
    fail "host $label compose config failed"
  grep -Fxq "$HA_EXPECTED_IMAGE" <<<"$resolved_images" || \
    fail "host $label compose does not resolve exact candidate image"

  local image_id image_digests
  image_id="$(ssh "${ssh_opts[@]}" "$host" "cd '$HA_DEPLOY_DIR' && ZWORKFORCE_IMAGE='$HA_EXPECTED_IMAGE' docker compose -f '$compose_file' images -q serve")" || \
    fail "host $label candidate image is not available"
  [[ -n "$image_id" ]] || fail "host $label serve image ID is empty"
  if [[ "$HA_IMAGE_PULL_POLICY" == "never" ]]; then
    # docker load intentionally leaves RepoDigests empty. The provenance file
    # is captured from the registry-backed image before docker save, copied
    # with the archive, and pinned by its own SHA-256 in the release env. The
    # loaded image ID must still match that pinned record.
    local provenance_sha provenance provenance_image provenance_digest provenance_image_id
    provenance_sha="$(ssh "${ssh_opts[@]}" "$host" "cd '$HA_DEPLOY_DIR' && sha256sum '$HA_IMAGE_PROVENANCE_FILE' | awk '{print \$1}'")" || \
      fail "host $label preloaded image provenance file is unavailable"
    [[ "${provenance_sha,,}" == "${HA_EXPECTED_IMAGE_PROVENANCE_SHA256,,}" ]] || \
      fail "host $label preloaded image provenance hash does not match the release record"
    provenance="$(ssh "${ssh_opts[@]}" "$host" "cd '$HA_DEPLOY_DIR' && cat '$HA_IMAGE_PROVENANCE_FILE'")" || \
      fail "host $label preloaded image provenance cannot be read"
    for field in IMAGE DIGEST IMAGE_ID; do
      [[ "$(grep -c "^${field}=" <<<"$provenance")" -eq 1 ]] || \
        fail "host $label preloaded image provenance must contain exactly one $field field"
    done
    if grep -Ev '^(IMAGE|DIGEST|IMAGE_ID)=' <<<"$provenance" | grep -q .; then
      fail "host $label preloaded image provenance contains an unexpected field"
    fi
    provenance_image="$(awk -F= '$1 == "IMAGE" {print substr($0, index($0, "=") + 1)}' <<<"$provenance")"
    provenance_digest="$(awk -F= '$1 == "DIGEST" {print substr($0, index($0, "=") + 1)}' <<<"$provenance")"
    provenance_image_id="$(awk -F= '$1 == "IMAGE_ID" {print substr($0, index($0, "=") + 1)}' <<<"$provenance")"
    [[ "$provenance_image" == "$HA_EXPECTED_IMAGE" ]] || \
      fail "host $label preloaded image provenance reference does not match exact candidate"
    [[ "$provenance_digest" == "$HA_EXPECTED_IMAGE_DIGEST" ]] || \
      fail "host $label preloaded image provenance digest does not match exact candidate"
    [[ "$provenance_image_id" == "$image_id" ]] || \
      fail "host $label loaded image ID does not match pinned provenance"
    note "host $label preloaded image ID and pinned candidate digest verified"
  else
    image_digests="$(ssh "${ssh_opts[@]}" "$host" "docker image inspect '$image_id' --format '{{join .RepoDigests \"\\n\"}}'")" || \
      fail "host $label image inspection failed"
    grep -Fq "$HA_EXPECTED_IMAGE_DIGEST" <<<"$image_digests" || \
      fail "host $label image digest does not match exact candidate"
  fi
}

verify_host A "$HA_HOST_A" "$HA_COMPOSE_FILE_A"
verify_host B "$HA_HOST_B" "$HA_COMPOSE_FILE_B"

# Query the authoritative shared PostgreSQL schema from VM-A. No local secret file
# is required and no DSN is printed. A release drill must create live lease/outbox
# ownership evidence before this verifier is run.
db_evidence="$(ssh "${ssh_opts[@]}" "$HA_HOST_A" "cd '$HA_DEPLOY_DIR' && docker compose -f '$HA_COMPOSE_FILE_A' exec -T serve python - <<'PY'
import os, sys
from datetime import datetime, timezone
try:
    import psycopg
except Exception as exc:
    print('ERROR psycopg unavailable:', exc)
    raise SystemExit(2)

dsn = os.environ.get('ZWORKFORCE_DATABASE_URL', '').strip()
if not dsn:
    print('ERROR ZWORKFORCE_DATABASE_URL missing')
    raise SystemExit(3)

conn = psycopg.connect(dsn, connect_timeout=5)
cur = conn.cursor()
cur.execute('SELECT name, owner, expires_at, heartbeat_at FROM service_leases3 ORDER BY name')
leases = cur.fetchall()
if not leases:
    print('ERROR service_leases3 has no rows')
    raise SystemExit(4)

now = datetime.now(timezone.utc)
lease_map = {str(row[0]): (str(row[1] or ''), str(row[2] or '')) for row in leases}
required = ('scheduler', 'outbox')
missing = [name for name in required if name not in lease_map]
if missing:
    print('ERROR required service lease rows missing: ' + ','.join(missing))
    raise SystemExit(6)

invalid = []
for name in required:
    owner, expires_at = lease_map[name]
    try:
        expires = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
    except ValueError:
        invalid.append(name + ':invalid-expiry')
        continue
    if not owner.startswith(name + '-'):
        invalid.append(name + ':invalid-owner')
    elif expires <= now:
        invalid.append(name + ':expired')
if invalid:
    print('ERROR invalid service lease evidence: ' + ','.join(invalid))
    raise SystemExit(7)

owners = {str(row[1]) for row in leases if row[1]}
print('lease_rows=' + str(len(leases)))
print('lease_owners=' + ','.join(sorted(owners)))
print('lease_services=' + ','.join(required))

cur.execute('SELECT claim_owner, COUNT(*) FROM outbox3 WHERE claim_owner IS NOT NULL AND claim_owner <> %s GROUP BY claim_owner ORDER BY claim_owner', ('',))
outbox = cur.fetchall()
if not outbox:
    print('ERROR outbox3 has no claimed ownership evidence; run the HA outbox drill first')
    raise SystemExit(5)
print('outbox_claim_owners=' + ','.join(str(row[0]) for row in outbox))
print('outbox_claim_rows=' + str(sum(int(row[1]) for row in outbox)))
conn.close()
PY" 2>&1)" || fail "shared PostgreSQL lease/outbox evidence query failed: $db_evidence"

note "$db_evidence"

grep -Fq "lease_services=scheduler,outbox" <<<"$db_evidence" || fail "required scheduler/outbox lease evidence missing"
grep -Fq "outbox_claim_owners=" <<<"$db_evidence" || fail "outbox3 claim_owner evidence missing"

# Metrics are mandatory for Stage E evidence; health-only fallback is not enough.
: "${ZWORKFORCE_METRICS_BEARER:?set ZWORKFORCE_METRICS_BEARER}"
for pair in "A:$HA_HOST_A" "B:$HA_HOST_B"; do
  label="${pair%%:*}"
  host="${pair#*:}"
  printf '%s\n' "$ZWORKFORCE_METRICS_BEARER" |
    ssh "${ssh_opts[@]}" "$host" '
      IFS= read -r metrics_bearer
      curl -fsS -H "Authorization: Bearer ${metrics_bearer}" http://127.0.0.1:9456/metrics |
        grep -E "zworkforce_|provider_|queue_|task_" >/dev/null
    ' || fail "host $label metrics endpoint missing expected series"
done

note "HA verification complete: shared lease/outbox ownership and both runtimes verified"
echo "VERIFY-HA: PASS"
