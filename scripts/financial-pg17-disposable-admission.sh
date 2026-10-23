#!/usr/bin/env bash
# Executes only against an attested disposable PostgreSQL 17 CI service.
set -Eeuo pipefail
umask 077
container="${POSTGRES_TEST_CONTAINER_ID:-}"
[[ "${Z_FINANCIAL_PG17_DISPOSABLE_ATTESTED:-}" == "true" ]] || { echo 'Disposable attestation required' >&2; exit 3; }
[[ "$container" =~ ^[0-9a-f]{12,64}$ ]] || { echo 'Disposable service ID required' >&2; exit 3; }
command -v docker >/dev/null || { echo 'Docker unavailable' >&2; exit 3; }
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
image="$(docker inspect --format '{{.Config.Image}}' "$container")"
label="$(docker inspect --format '{{index .Config.Labels "zeaz.financial.acceptance"}}' "$container")"
db_env="$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$container")"
[[ "$image" == "postgres:17-alpine" && "$label" == "disposable" ]] || { echo 'Untrusted service image or label' >&2; exit 3; }
grep -Fxq 'POSTGRES_DB=zeaz_financial_acceptance' <<< "$db_env" || { echo 'Untrusted database' >&2; exit 3; }
version="$(docker exec "$container" psql -X -U postgres -d zeaz_financial_acceptance -Atqc 'SHOW server_version_num')"
[[ "$version" =~ ^17[0-9]{4}$ ]] || { echo 'PostgreSQL major version mismatch' >&2; exit 3; }
# A missing zeaz_financial schema does not imply an empty database. Refuse any
# pre-existing user schema, public relation/function/type, or user extension.
existing="$(docker exec "$container" psql -X -U postgres -d zeaz_financial_acceptance -Atqc "
SELECT (
  EXISTS (
    SELECT 1 FROM pg_namespace
    WHERE nspname !~ '^pg_' AND nspname NOT IN ('public', 'information_schema')
  ) OR EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
  ) OR EXISTS (
    SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
  ) OR EXISTS (
    SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE n.nspname = 'public'
  ) OR EXISTS (
    SELECT 1 FROM pg_extension WHERE extname <> 'plpgsql'
  )
)::int;
")"
[[ "$existing" == "0" ]] || { echo 'Acceptance database contains pre-existing user objects' >&2; exit 3; }
for file in services/billing-ledger/migrations/0001_financial_pg17_disposable.sql services/billing-ledger/acceptance/pg17_disposable_contract.sql; do
  docker exec -i "$container" psql -X -v ON_ERROR_STOP=1 -U postgres -d zeaz_financial_acceptance < "$root/$file" >/dev/null
done
# Competing synthetic inserts must produce exactly one record and one audit event.
statement="SET ROLE zeaz_financial_runtime; BEGIN; SET LOCAL zeaz.tenant_id='tenant-concurrent'; INSERT INTO zeaz_financial.usage_events VALUES ('tenant-concurrent','usage-1','key-1','subject','model',1,1,now()); COMMIT;"
set +e
docker exec "$container" psql -X -v ON_ERROR_STOP=1 -U postgres -d zeaz_financial_acceptance -c "$statement" >/dev/null 2>&1 & pid1=$!
docker exec "$container" psql -X -v ON_ERROR_STOP=1 -U postgres -d zeaz_financial_acceptance -c "$statement" >/dev/null 2>&1 & pid2=$!
wait "$pid1"; rc1=$?
wait "$pid2"; rc2=$?
set -e
if ! { [[ "$rc1" == 0 && "$rc2" != 0 ]] || [[ "$rc1" != 0 && "$rc2" == 0 ]]; }; then
  echo 'Concurrent identity contract failed' >&2; exit 1
fi
counts="$(docker exec "$container" psql -X -U postgres -d zeaz_financial_acceptance -Atqc "SELECT (SELECT count(*) FROM zeaz_financial.usage_events WHERE tenant_id='tenant-concurrent')::text || ':' || (SELECT count(*) FROM zeaz_financial.audit_events WHERE tenant_id='tenant-concurrent')::text")"
[[ "$counts" == '1:1' ]] || { echo 'Concurrent audit invariant failed' >&2; exit 1; }
printf 'PG17_FINANCIAL_DISPOSABLE_ACCEPTANCE_PASS\n'
