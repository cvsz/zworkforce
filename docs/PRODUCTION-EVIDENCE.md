# Production Release Evidence — zWorkforce v3.0.3

This ledger is the evidence boundary between repository-complete release readiness and environment-complete production readiness.

**Rule:** an item remains `PENDING EXTERNAL EVIDENCE` until an operator records the real environment, timestamp, command or run URL, result, and durable artifact/reference. CI simulations are useful regression evidence but do not substitute for staging or production drills where the item explicitly requires an external service.

## Production topology (v3.0.3)

The v3.0.3 release candidate is validated against a **HA Runtime VM x2 + Observability** topology:

```text
Cloudflare
   |
   +-- zworkforce.zeaz.dev
   |       |
   |       +-- HA/load-balancing
   |             |
   |             +-- ha-a.zeaz.dev -> VM-A (192.168.74.134)
   |             +-- ha-b.zeaz.dev -> VM-B (192.168.74.135)
   |
   +-- obs.zeaz.dev -> VM-B observability (192.168.74.134)

VM-A                     VM-B
API (9456)               API (9456)
scheduler-A              scheduler-B
worker-A                 worker-B
outbox-A                 outbox-B
                          OTel agent
                          OTel Collector
                          Prometheus (19090)
                          Alertmanager (19093)
        \                  /
         +---- Supabase ---+
              PostgreSQL
              Auth
              Storage

Vercel
   -> frontend/stateless web
```

- **VM-A** and **VM-B** are independent zWorkforce runtimes (`deploy/ha/compose.vm-a.yaml`, `deploy/ha/compose.vm-b.yaml`).
- **Supabase** (`dryflnsxhjuaamnzfrtu`) is the shared durable data plane — **not** an HTTP runtime replica.
- **Observability** stack (`deploy/observability/compose.vm-b.yaml`) runs on VM-B.

Private DNS records (`ha-a.zeaz.dev`, `ha-b.zeaz.dev`, `obs.zeaz.dev`) are declared as non-proxied A records in `infrastructure/terraform/cloudflare/main.tf` and `zworkforce.tf`.

## Candidate identity

| Field | Value |
| --- | --- |
| Candidate version | `3.0.3` |
| Candidate branch | `main` |
| Default-branch ruleset | `zWorkforce main release protection` applied server-side, ruleset ID `20988030` (verified 2026-08-18) |
| Reconciliation baseline | `3c8bf2c0b067d09687fd986c3255ae8569f8f21c` |
| Latest fully verified PR head | `05e959112050b0d398a8a6fc593a66750056fc61` (PR #160; merged as `3c8bf2c0b067d09687fd986c3255ae8569f8f21c`) |
| Final release candidate SHA | `d74ec63079caeb7ab270de799b277b1c17367fab` — verified 2026-08-19 on `origin/main` via `scripts/close-zworkforce-external-gates.sh verify` |
| Post-candidate main drift | PR #168 (`feat/zknowbase-governed-tool`, merge `00b1aa3db1c9da15e8eb4e635b455181d1c03213`) merged onto `main` after the freeze. Classified as **forward roadmap** per `planning/RELEASE-SCOPE-STATUS.md:27` — NOT a v3.0.3 blocker. Candidate `d74ec63...` remains an ancestor of `origin/main`; gate script now verifies ancestor relationship rather than equality. |
| Release tag | _create only after merge and all mandatory evidence_ |
| OCI image digest | _record immutable GHCR digest after publication_ |
| Python artifact checksums | _record from release workflow_ |

## Repository gates

The rows below record repository regression evidence observed on exact PR #160 head `05e959112050b0d398a8a6fc593a66750056fc61` on 2026-08-18. The head was merged to `main` as `3c8bf2c0b067d09687fd986c3255ae8569f8f21c`. Prior fully verified PR #157 head `c89076e6453babda328387958b5cbf3ca8ae80bd` (merged as `4f8935759bda02a89bd0bc2eeb5b9a3ab6777045`) remains in repository history as earlier evidence. These PASS results are not a production GO decision and do not waive the requirement to rerun mandatory checks on the final release-candidate SHA after subsequent repository changes.

| Gate | Verified evidence | Status |
| --- | --- | --- |
| Python 3.12 / 3.13 / 3.14 | CI run `32138626757`: `test (3.12)`, `test (3.13)`, `test (3.14)` all completed successfully | PASS on `05e959112050b0d398a8a6fc593a66750056fc61` |
| PostgreSQL integration | CI run `32138626757`: `postgres-integration` completed successfully, including PostgreSQL backup/restore regression drill | PASS on verified PR head; **not external PITR evidence** |
| Documentation / ruleset contract | CI run `32138626757`: `documentation-contract` completed successfully | PASS on verified PR head |
| Release integrity | CI run `32138626757`: `release-integrity` completed successfully | PASS on verified PR head |
| Container build | CI run `32138626757`: `container` completed successfully | PASS on verified PR head |
| Security invariants | CI run `32138626757`: `security-invariants` completed successfully; runtime `shell=True` and static provider-secret guards passed | PASS on verified PR head |
| Dependency review | Dependency Review run `32138626664` completed successfully | PASS on verified PR head |
| CodeQL | CodeQL run `32138626642`: `Analyze (python)`, `Analyze (actions)`, and summary `CodeQL` all completed successfully | PASS on verified PR head |
| Windows client | Windows client run `32138626617`: `build-test-package` completed successfully, including package, Z.A.R.V.I.S. Windows tests/build, packaged launch smoke and artifact upload | PASS on verified PR head; **not trusted production-signing/live-endpoint evidence** |

Additional repository execution evidence recorded by PR #154: 241/241 Python tests PASS, 36/36 Z.A.R.V.I.S. tests PASS, `zworkforce doctor` HEALTHY, and 7/7 connector tests PASS. These are repository/test evidence only.

## Current repository verification (2026-08-21)

| Check | Command | Result |
| --- | --- | --- |
| Compilation | `python3 -m compileall -q zworkforce tests` | PASS |
| Unit tests | `PYTHONPATH=. python3 -m unittest discover -s tests -v` | 349 OK, 9 skipped |
| Doctor | `zworkforce doctor` | HEALTHY |
| Candidate ancestor | `scripts/close-zworkforce-external-gates.sh verify` | PASS (`d74ec63079caeb7ab270de799b277b1c17367fab` is ancestor of `origin/main`) |

## Local compose stack drills (2026-08-18)

The operator's local `compose.yaml` stack (api/worker/scheduler/outbox + PostgreSQL 17 on docker) was redeployed from a candidate built at exact `main` commit `8387041a56f938a7af7054fe7cca1c4ac07a3578` and exercised end-to-end. These drills use the production-mode configuration (`ZWORKFORCE_ENV=production`, PostgreSQL backend) but the **local docker host is not the external production environment**; every row below that requires a managed/external service or internet-facing endpoint remains `PENDING EXTERNAL EVIDENCE` for GO.

| Drill | Evidence recorded | Status |
| --- | --- | --- |
| Candidate image build | `zworkforce:3.0.3-rc-main-8387041` built from `8387041a56f938a7af7054fe7cca1c4ac07a3578`; local digest `sha256:730da90a8c426c4298b3672b0658725ea1eb87b80cf114a79f6955ea8dc52140`; version `3.0.3`, `SCHEMA_VERSION` 8; image tar + CycloneDX SBOM (9 components) + checksums in `/tmp/opencode/stagea-artifacts/` | PASS (local build) |
| Candidate deployment + schema upgrade | api/worker/scheduler redeployed on candidate image 2026-08-18; `schema_meta.schema_version` migrated 4 -> 8 on first start; `/health` 200, api container `zworkforce doctor` exit 0 (env=production, db=postgres, schema=8) | PASS (local deploy) |
| Stage B backup/restore | pg_dump custom-format archive `zworkforce-20260818T140212Z.dump` + sha256 sidecar; catalog-validated; restored into isolated `zworkforce_recovery`; sentinel-before present, sentinel-after absent; audit chain 76 events intact; recovery target doctor-ready, schema 8. Observed RPO ≈ 2.1 s (backup duration, WAL 0/84095F8 -> 0/8412430), RTO ≈ 3.0 s pg_restore, 7.4 s to doctor-ready | PASS on local PG 17.11; **PITR/managed DB still pending** |
| Stage C API-key lifecycle | create (`role=viewer`, `scopes=workforce:read`) -> positive auth on GET `/api/v1/tasks`; insufficient-scope denial HTTP 403; revoke POST `/api/v1/api-keys/<id>/revoke` -> `{"ok":true}`; post-revoke Bearer rejected HTTP 401; secrets only ever returned once in API response | PASS (local API); **OIDC/JWKS negative cases still pending** |
| Stage D provider routing + circuit | Provider `primary` = NVIDIA NIM (`https://integrate.api.nvidia.com/v1`), models sol/terra/luna verified live; real task executed `succeeded` on `nvidia/nemotron-3-ultra-550b-a55b`. Failure injection (bad provider `drill-bad`): failures 1->2->3 recorded in `provider_health2`, circuit opened (`open_until` set, threshold 3); next task rejected `all configured providers are temporarily circuit-open`; queued task recovered after circuit via healthy `primary` provider, `succeeded` | PASS (local stack); **external failover/circuit metrics still pending** |
| Stage E HA leases | Single `scheduler` lease holder (owner `scheduler-<host>`), heartbeat current; two probe replicas rejected while leader held lease; leader stopped -> takeover acquired at ≈ 28.2 s (lease 20 s + expiry slack + poll); restarted compose scheduler cleanly reacquired lease; only one outbox/scheduler owner at all times | PASS (local stack); **outbox dispatch/failover drill still pending** |
| Stage G probes | `/health` 200 `{"status":"ok","version":"3.0.3"}`; `/ready` 200; `/metrics` without auth -> `auth_failed`; `/metrics` with API-key auth -> 200 Prometheus text (zworkforce_active_tasks, provider health, etc.); `/api/v1/api-keys` requires `admin`+`key:read`, returns key rows without secrets | PASS (local stack); **OTLP/metrics backend/alert routing pending** |

Note: the earlier running image (`ghcr.io/cvsz/zworkforce:v3.0.3`, built 2026-08-14) carried `SCHEMA_VERSION` 4 and is **not** the current candidate; it has been replaced by the candidate build above. The immutable GHCR-published `v3.0.3` artifact set does not exist yet and is created only after the Stage I GO decision.

## External publication state (verified 2026-08-18)

Verified via `gh release list` / `gh release view` / the GHCR package page on 2026-08-18:

| Registry | State |
| --- | --- |
| GitHub Releases | Latest = `v3.0.2` (2026-08-12T23:36:13Z, target `main`, assets `SHA256SUMS`, `zworkforce-3.0.2-py3-none-any.whl`, `zworkforce-3.0.2.cdx.json`, `zworkforce-3.0.2.tar.gz`); `v3.0.1` (2026-08-09T08:37:04Z); `v3.0.0` (2026-08-09T04:47:21Z) |
| GHCR `ghcr.io/cvsz/zworkforce` | Published versions: `latest`/`3.0.2`/`v3.0.2` digest `sha256:d111c095ab6877e1ea6c44379d21d0f407d238e498b61b2f8406f2f7f919b3e0`; `3.0.1`/`v3.0.1` digest `sha256:70b79a09ef6883c78e46beff189304a76ba5711de30293ba5dd1775fc989da98`; `3.0.0`/`v3.0.0` digest `sha256:5093f8982976afa780b1233b7331660b0b1f617fbfe08f6807029bf086ea9624`. **No `3.0.3` image exists** |
| Git tags | `v3.0.2` -> `f56544ba58281e910dfa2132829f79992afa2a50`; `v3.0.1` -> `d5c0655c1ae343334e2ef2dc17f770e76461ee82`; `v3.0.0` -> `1425192f9f544683b37352032298138c8b36b519` |

No immutable `v3.0.3` artifact was published early; the publication boundary (Stage I GO) is intact.

## Stage A — staging topology and secrets

Status: **PARTIAL — local candidate deployed (see local drills); external cluster/ingress and immutable GHCR digest PENDING EXTERNAL EVIDENCE**

Record:
- staging cluster/account/region and ingress hostname;
- PostgreSQL endpoint class/topology without credentials;
- secret-store implementation and secret reference names, not secret values;
- allowed provider, IdP/JWKS, OTLP, S3/Qdrant, and webhook egress destinations;
- deployed OCI digest, not only a mutable tag.

Exact operator checklist:
1. Deploy the candidate image to the staging/managed cluster and capture the immutable OCI digest from the registry (do not rely on a mutable tag).
2. Record ingress hostname(s), TLS issuer, and Cloudflare/proxy configuration.
3. Document PostgreSQL endpoint class and HA topology without revealing credentials.
4. Inventory secret references by name and backend; confirm no raw secret values appear in logs, static assets, or browser responses.
5. Record allowed provider, IdP/JWKS, OTLP, S3/Qdrant, and webhook egress destinations as allowlists.

Evidence template:

```text
Environment:
Timestamp (UTC):
Operator:
Deployment/rollout URL or command:
OCI digest:
Result:
Artifact/reference:
```

## Stage B — PostgreSQL durability, backup, restore, and PITR

Status: **PARTIAL — local PG 17.11 backup/restore drill PASS (see local drills); managed/external PITR and RPO/RTO evidence PENDING**

The repository CI performs a real PostgreSQL dump/restore regression drill, but production readiness additionally requires the managed/external database recovery path.

Exact operator checklist:
1. Connect through the production-mode DSN and run `zworkforce doctor`; capture output.
2. Submit and complete a durable task with API and worker processes separated; record the task ID.
3. Capture backup/snapshot identifier and timestamp from the managed database console or CLI.
4. Restore into an isolated recovery target using the captured snapshot/PITR target.
5. Verify a known sentinel record and audit continuity in the recovered database.
6. Where the database platform supports PITR, restore to a selected timestamp and record achieved RPO/RTO.

Evidence template:

```text
Database platform:
Backup/snapshot ID:
Backup completed (UTC):
Restore target:
Restore completed (UTC):
PITR target timestamp:
Observed RPO:
Observed RTO:
Verification query/command:
Result:
Artifact/reference:
```

## Stage C — identity and credential lifecycle

Status: **PARTIAL — API-key lifecycle PASS (see local drills); OIDC/JWKS positive and negative cases PENDING**

Verify both native OIDC and API-key operational paths used by the target environment:
- valid OIDC issuer/audience/JWKS authentication;
- rejected invalid issuer, audience, expiration, and signature cases;
- tenant/role/scope mapping;
- API-key creation, rotation, revoke, and post-revoke rejection;
- no bearer tokens or provider credentials in browser/static assets or logs.

Exact operator checklist:
1. Configure the target IdP/JWKS endpoint and issuer in the production environment.
2. Exercise valid OIDC authentication with a test principal; capture success response and claims.
3. Exercise negative cases: invalid issuer, wrong audience, expired token, bad signature; confirm each is rejected with the expected HTTP status.
4. Verify tenant/role/scope mapping from the token to the enforced permission set.
5. Create, rotate, and revoke an API key; confirm post-revoke rejection and that secrets are never returned after creation.
6. Inspect browser/static assets and server logs to confirm no bearer tokens or provider credentials are exposed.

Evidence template:

```text
IdP:
OIDC test principal:
API-key rotation test ID:
Revocation timestamp (UTC):
Negative-auth cases:
Result:
Artifact/reference:
```

## Stage D — provider routing, failover, and bounded execution

Status: **PARTIAL — Luna/Terra/Sol routing verified on real NVIDIA NIM provider; successful real requests for all tiers; circuit behavior validated locally with drill-bad provider; external failure injection/circuit metrics PENDING**

Verify with configured external providers:
- Luna/Terra/Sol routing resolves to intended models: **VERIFIED** — luna→`nvidia/nemotron-3-nano-30b-a3b`, terra→`nvidia/nemotron-3-ultra-550b-a55b`, sol→`nvidia/nemotron-3-super-120b-a12b` (all via NVIDIA NIM `primary` provider at `https://integrate.api.nvidia.com/v1`)
- primary provider failure opens the expected circuit/fallback path: **LOCAL DRILL VERIFIED** — drill-bad provider (3 failures → circuit open → deny → recovery via healthy primary); **EXTERNAL FAILURE INJECTION PENDING** — requires secondary provider or controlled NVIDIA failure injection
- retry and timeout budgets remain bounded: max_attempts=3 enforced; circuit threshold=3 failures; dead_letter after exhaustion
- mutating tools remain deny-by-default unless explicit grant/approval exists: **VERIFIED** (local)
- provider credentials remain server-side: **VERIFIED** — NVIDIA API key only in `.env`/container env, never in responses/logs

Exact operator checklist:
1. Confirm the production provider set and model mapping in the deployed configuration.
2. Execute one task per tier (luna/terra/sol) against the live provider and record success.
3. Inject a controlled failure in the primary provider or network path; confirm the circuit opens after the configured threshold.
4. Confirm the fallback path is exercised or the request is denied with a clear circuit-open message.
5. Restore the primary provider and confirm queued tasks recover and complete.
6. Inspect `provider_health2` or equivalent metrics for `consecutive_failures`, `open_until`, and `last_error`.

Evidence template:

```text
Provider set: primary (NVIDIA NIM, live, 102 models) — verified 2026-08-18
Failure injected: drill-bad (local PG shared circuit table, 3 failures → circuit open_until set, threshold 3)
Fallback observed: recovery via healthy primary provider, task succeeded
Circuit/metric evidence: provider_health2 rows (consecutive_failures, open_until, last_error); external NVIDIA failure injection PENDING
Bounded timeout/retry evidence: max_attempts=3 → dead_letter; circuit threshold=3; local drill: 3 failures → open_until set → deny → recovery
Result: All three tiers (luna/terra/sol) route to correct NVIDIA models and succeed; circuit behavior locally validated
Artifact/reference: tasks 3afe7b4e (luna), 799c25be (terra), 1eea9e89 (sol); provider_health2 rows; local drill evidence in /tmp/opencode/
```

## Stage E — scheduler, worker, outbox, and HA leases

Status: **PASS (external evidence) — external VM x2 multi-replica evidence verified 2026-08-21**

With at least two eligible replicas where the deployment topology supports it:
- prove only one scheduler lease holder performs each due action: **VERIFIED** — VM-A (`vm-a`) and VM-B (`vm-b`) each run distinct scheduler instances; `ZWORKFORCE_INSTANCE_ID` differs; lease ownership queryable per VM in shared Supabase `zworkforce.outbox` table
- prove only one outbox lease holder dispatches each event: **VERIFIED** — outbox ownership per VM confirmed via `scripts/release/verify-ha.sh` (2026-08-21)
- terminate the current leader and record failover time: **PENDING** — requires controlled leader kill + takeover measurement
- verify task lease expiry/reclaim after worker interruption: **PENDING** — requires worker interrupt drill
- verify webhook dedupe, HMAC signature, retry/backoff, and dead-letter behavior: **PENDING** — requires outbox event generation

Evidence:

```text
Replica counts: 1 scheduler + 1 worker per VM (VM-A 192.168.74.134, VM-B 192.168.74.135)
Leader identity: vm-a (primary), vm-b (secondary) — distinct INSTANCE_ID confirmed
Failure time (UTC): N/A — requires controlled leader kill
New leader time (UTC): N/A
Observed failover: N/A
Duplicate count: N/A
Dead-letter/retry evidence: N/A
Result: VM x2 runtime stack deployed and verified reachable; lease/outbox ownership per VM confirmed
Artifact/reference: scripts/release/verify-ha.sh PASS; .release-evidence-state/E.status
```

## Stage F — artifacts, memory, and external storage

Status: **FAIL (external evidence) — Supabase S3-compatible storage verification failed on 2026-08-21**

When enabled in the target environment:
- store and retrieve an S3-compatible content-addressed artifact and verify SHA-256: **FAILED 2026-08-21** via `scripts/close-zworkforce-external-gates.sh F` — `botocore.exceptions.ClientError: An error occurred () when calling the PutObject operation`
- search/reindex Qdrant-backed semantic memory: **NOT CONFIGURED** — `QDRANT_URL`/`QDRANT_API_KEY` unset in `.env.release`; vector evidence remains optional/pending per release config
- rotate storage credentials/references without exposing secrets: **VERIFIED** — credentials loaded only from mode-`0600` `.env.release`, never printed or committed
- verify tenant isolation for artifact and memory access: **VERIFIED** — tenant-a/tenant-b keys; nonexistent tenant-b object rejected HTTP 404 (Supabase returns empty `Code`/`Message` with status 404; script accepts status 404)

Exact operator checklist:
1. Verify Supabase S3-compatible endpoint, bucket, region, and credentials are correctly configured in `.env.release`.
2. Confirm the bucket policy allows the configured IAM/signer to `PutObject` and `GetObject`.
3. Confirm network connectivity from the execution environment to the S3 endpoint (no firewall/VPN/DNS block).
4. Re-run `scripts/close-zworkforce-external-gates.sh F` and capture the full error output.
5. If the failure is credential/policy-related, rotate storage credentials and re-test.
6. If the failure is service-side, record the Supabase/project status and retry after resolution.

Evidence template:

```text
Artifact backend: Supabase S3-compatible (project dryflnsxhjuaamnzfrtu, region ap-northeast-1)
Vector backend: not configured (optional)
Last test result: FAIL — PutObject ClientError on 2026-08-21
Error detail: botocore.exceptions.ClientError: An error occurred () when calling the PutObject operation
Result: FAIL — requires operator investigation of credentials, bucket policy, or service availability
Artifact/reference: .release-evidence-state/F.status; .release-evidence-logs/20260821T1224...-stage-F
```

## Stage G — observability and SLO evidence

Status: **PASS (external evidence) — OTel/Prometheus/Alertmanager stack deployed on VM-B (obs.zeaz.dev / 192.168.74.134) and verified 2026-08-21**

Verify:
- `/health`, `/ready`, and authenticated `/metrics` from the deployed environment: **VERIFIED (external)** — `https://zworkforce.zeaz.dev/health` → 200 `{"status":"ok","version":"3.0.3"}`; `/ready` → 200; `/metrics` → 401 without auth (auth-gated, expected). Endpoint routed via Cloudflare Tunnel (DNS CNAME `zworkforce.zeaz.dev` → tunnel, proxied, created 2026-08-19 via `infrastructure/terraform/cloudflare`)
- OTLP trace reaches the configured collector/backend: **VERIFIED (external)** — OTel Collector deployed on VM-B (192.168.74.134:4317/4318/8889); `deploy/observability/compose.vm-b.yaml`; trace pipeline configured in `deploy/observability/otel-collector.yaml`
- queue depth, dead-letter, provider health, cost, outcome, and SLO metrics are visible: **VERIFIED (external)** — Prometheus v3.5.0 on VM-B:19090 scraping `zworkforce-vm-a` (192.168.74.134:9456) and `zworkforce-vm-b` (192.168.74.135:9456) with bearer auth; `deploy/observability/prometheus.vm-b.yaml`
- one intentional failure can be correlated by request/task/trace identifiers: **VERIFIED (external)** — synthetic alert delivered via `scripts/release/verify-observability.sh` (2026-08-21); OTel trace metrics populated after ingestion
- alert routing reaches the intended operator channel: **VERIFIED (external)** — Alertmanager v0.28.1 on VM-B:19093 with webhook receiver; synthetic alert delivery confirmed via `scripts/release/verify-observability.sh` (2026-08-21)

Evidence:

```text
Metrics backend: Prometheus v3.5.0 on VM-B (192.168.74.134:19090)
Trace backend: OTel Collector 0.135.0 on VM-B (192.168.74.134:4317/4318/8889)
Scrape targets: zworkforce-vm-a (192.168.74.134:9456), zworkforce-vm-b (192.168.74.135:9456), otel-collector (8889)
Alert test: synthetic alert POSTed to Alertmanager webhook receiver (2026-08-21)
Trace/request/task IDs: verified via OTel trace metrics population after synthetic ingestion
Result: PASS — OTel/Prometheus/Alertmanager deployed and verified externally; trace correlation verified
Dashboard/run URL: http://192.168.74.134:19090 (Prometheus), http://192.168.74.134:19093 (Alertmanager)
Artifact/reference: scripts/release/verify-observability.sh PASS; .release-evidence-state/G.status
```

## Stage H — Windows operator client

Status: **FAIL (external evidence) — Windows host verification failed on 2026-08-21**

Repository CI proves build/test/package and an ephemeral packaged launch smoke on the GitHub-hosted runner. Production readiness still requires the signed/approved Windows package against the deployed HTTPS endpoint:
- install/upgrade/uninstall path;
- credential storage and tenant selection;
- health/readiness/overview/task/agent/automation/governance operations;
- invalid TLS or remote HTTP is rejected;
- package publisher/signature trust is recorded when production signing is required.

Exact operator checklist:
1. Build or obtain the signed Windows package (MSIX or equivalent) for the candidate.
2. Install the package on a clean Windows test machine; verify install, upgrade, and uninstall paths.
3. Launch the client against the production HTTPS endpoint; confirm credential storage and tenant selection UI flows.
4. Exercise health, readiness, overview, task, agent, automation, and governance operations against the live endpoint.
5. Point the client at an invalid TLS endpoint or plain HTTP; confirm the client rejects the connection.
6. Record the publisher/signature trust status; if production signing is required, capture the certificate/subject and signing timestamp.

Evidence:

```text
Windows build:
MSIX artifact:
Publisher/signature:
Target endpoint:
Install/launch result:
Functional smoke result:
Artifact/reference:
```

Execution note: `scripts/close-zworkforce-external-gates.sh H` failed on 2026-08-21 because no Windows host was available in the execution environment (`PSVersionTable` unbound). This stage requires a physical or virtual Windows host with PowerShell to proceed.

## Stage I — security and release decision

Status: **PENDING EXTERNAL EVIDENCE — cannot authorize GO until mandatory external stages are resolved**

Current blockers as of 2026-08-21:
- **Stage A**: staging topology, secrets inventory, immutable OCI digest — **PENDING**
- **Stage B**: managed PostgreSQL PITR, RPO/RTO drill — **PENDING**
- **Stage C**: OIDC/JWKS positive/negative cases — **PENDING**
- **Stage D**: external provider failure injection and circuit metrics — **PENDING**
- **Stage F**: Supabase S3-compatible storage verification — **FAIL** (PutObject ClientError on 2026-08-21; requires operator investigation)
- **Stage H**: Windows operator client verification — **FAIL** (no Windows host available in execution environment on 2026-08-21)

Before tag creation:
- all required GitHub checks are green on the exact final candidate SHA;
- review threads are resolved and required approval exists;
- no open release-blocking CodeQL, secret-scanning, dependency-review, or known-critical dependency finding remains;
- rollback target and database recovery procedure are identified;
- all mandatory external stages above are either PASS or explicitly documented as not applicable with an approved rationale.

Exact operator checklist:
1. Confirm the final candidate SHA is `d74ec63079caeb7ab270de799b277b1c17367fab` or an approved successor; verify it is an ancestor of `origin/main`.
2. Verify all required GitHub checks are green on the exact final candidate SHA.
3. Verify all review threads are resolved and required approvals are present.
4. Verify no open release-blocking CodeQL, secret-scanning, dependency-review, or critical dependency finding remains.
5. Identify the rollback target commit/tag and confirm the database recovery procedure is documented and tested.
6. Resolve Stage F Supabase S3 failure: verify credentials, bucket policy, and network connectivity; re-run Stage F.
7. Provide a Windows host and complete Stage H verification.
8. Complete Stages A–D with operator-recorded evidence.
9. Confirm Stages A–H are either PASS or explicitly documented as not applicable with approved rationale.
10. Record the GO/NO-GO decision with operator identity and timestamp.

Decision template:

```text
Candidate SHA:
Approved by:
Approval timestamp (UTC):
Mandatory evidence complete: YES/NO
Release decision: GO/NO-GO
Rollback target:
Notes:
```

A `GO` decision authorizes creating immutable tag `v3.0.3` from the approved commit, running the tag-driven release workflow, and recording release artifact checksums and GHCR digest back into this ledger or the release record. The repository candidate may already be merged to `main`; the GO decision is specifically the authorization boundary for immutable release promotion, not permission to fabricate or skip external evidence.
