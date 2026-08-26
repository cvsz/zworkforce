# Production Release Evidence — zWorkforce v3.0.4

`v3.0.3` is an immutable published predecessor. It was published before the
external GO evidence was complete and its exact HA image verification exposed
two production defects: the image omitted the S3 runtime extra and its HA
healthcheck invoked `curl`, which is not installed in the image. It must not be
retagged or treated as the production promotion target. This ledger tracks the
corrective `v3.0.4` candidate.

This ledger is the evidence boundary between repository-complete release readiness and environment-complete production readiness.

**Rule:** an item remains `PENDING EXTERNAL EVIDENCE` until an operator records the real environment, timestamp, command or run URL, result, and durable artifact/reference. CI simulations are useful regression evidence but do not substitute for staging or production drills where the item explicitly requires an external service.

## Production topology (v3.0.4)

The v3.0.4 release candidate is validated against a **HA Runtime VM x2 + Observability** topology:

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
- **Supabase** (`qhprcfdgajhmdzvnsffb`) is the shared durable data plane — **not** an HTTP runtime replica.
- **Observability** stack (`deploy/observability/compose.vm-b.yaml`) runs on VM-B.

Private DNS records (`ha-a.zeaz.dev`, `ha-b.zeaz.dev`, `obs.zeaz.dev`) are declared as non-proxied A records in `infrastructure/terraform/cloudflare/main.tf` and `zworkforce.tf`.

## Candidate identity

| Field | Value |
| --- | --- |
| Candidate version | `3.0.4` |
| Candidate branch | `fix/ha-verifier-sql-quoting` (PR #181; pending merge to `main`) |
| Default-branch ruleset | `zWorkforce main release protection` applied server-side, ruleset ID `20988030` (verified 2026-08-25) |
| Reconciliation baseline | `e15b7d60c58c58e75ee031ed8b9c6fc360257cbd` (merged PR #180; v3.0.4 production-image/HA fix line) |
| Latest candidate head | `453c8195b7ebf5e4d86f380bff94572c2b4451` — signed PR #181 head; required `policedbc` review pending |
| Final release candidate SHA | _pending merge and exact-candidate CI_ |
| Post-candidate main drift | _record after the follow-up PR merges; external evidence must bind to that exact SHA_ |
| Release tag | _create only after merge and all mandatory evidence_ |
| OCI image digest | _record immutable GHCR digest after publication_ |
| Python artifact checksums | _record from release workflow_ |

## Repository gates

The v3.0.3 repository gate results below are historical predecessor evidence.
The v3.0.4 follow-up must repeat the required checks on its exact merged SHA;
local validation of the corrective image fix is recorded in the follow-up PR.

| Gate | Verified evidence | Status |
| --- | --- | --- |
| Python 3.12 / 3.13 / 3.14 | CI run `32892904620`: `test (3.12)`, `test (3.13)`, `test (3.14)` all completed successfully | PASS on exact candidate |
| PostgreSQL integration | CI run `32892904620`: `postgres-integration` completed successfully, including PostgreSQL backup/restore regression drill | PASS on exact candidate; **not external PITR evidence** |
| Documentation / ruleset contract | CI run `32892904620`: `documentation-contract` completed successfully | PASS on exact candidate |
| Release integrity | CI run `32892904620`: `release-integrity` completed successfully | PASS on exact candidate |
| Container build | CI run `32892904620`: `container` completed successfully | PASS on exact candidate |
| Security invariants | CI run `32892904620`: `security-invariants` completed successfully; runtime `shell=True` and static provider-secret guards passed | PASS on exact candidate |
| Dependency review | PR #178 run `32892220435` completed successfully on reviewed head `a4db916e…`; the workflow is pull-request scoped | PASS for merge review; exact-main rerun remains a release-process improvement |
| CodeQL | CodeQL run `32892904633`: `Analyze (python)`, `Analyze (actions)`, and summary `CodeQL` all completed successfully | PASS on exact candidate |
| Z.A.R.V.I.S. package gates | ZARVIS run `32892904642`: `node-workspace`, `migration-contract`, `zarvis-api`, and `zarvis-windows-linux-restore` all completed successfully | PASS on exact candidate |
| Windows client | Windows client run `32892904646`: `build-test-package` completed successfully, including package, Z.A.R.V.I.S. Windows tests/build, packaged launch smoke and artifact upload | PASS on exact candidate; **not trusted production-signing/live-endpoint evidence** |

Additional repository execution evidence recorded by PR #154: 241/241 Python tests PASS, 36/36 Z.A.R.V.I.S. tests PASS, `zworkforce doctor` HEALTHY, and 7/7 connector tests PASS. These are repository/test evidence only.

## Latest external gate attempt for published v3.0.3 (2026-08-25)

The operator reran the external gates against predecessor candidate
`4ffdfa6e...`. None of these attempts authorizes a production GO. The exact
published `ghcr.io/cvsz/zworkforce:3.0.3` image was subsequently inspected and
failed runtime readiness because the S3 extra was absent and the HA healthcheck
called missing `curl`; the corrected image is therefore being released as
`v3.0.4`.

| Gate | Result | Evidence / next action |
| --- | --- | --- |
| E | FAIL | Both hosts were reachable, but the published predecessor image failed readiness: its S3 backend dependency was absent and its HA healthcheck called unavailable `curl`. Rerun against the immutable `v3.0.4` image and corrected HA Compose files. |
| F | FAIL | Supabase S3 `PutObject` returned HTTP 403. Regenerate/verify the S3 access key, secret, endpoint, and region from the Supabase S3 configuration, then rerun. |
| G | FAIL | The first rerun used a generated single `zworkforce` job while the verifier required `zworkforce-vm-a` and `zworkforce-vm-b`; the gate generator is now corrected, but exact-candidate observability evidence must be rerun. |
| H | FAIL | Windows checkout was `6f6fe3f...`, not the exact candidate `4ffdfa6e...`; sync the Windows checkout to the candidate before rebuilding/signing. |

The Stage G generator now mounts both the metrics bearer and Alertmanager webhook as remote secret files rather than embedding them in generated YAML. The bearer used by the failed run was present in a generated remote configuration and must be rotated before the next observability run.

## Corrective v3.0.4 candidate gate follow-up (2026-08-25 — 2026-08-26)

The signed PR #181 head is `453c8195b7ebf5e4d86f380bff94572c2b4451`. The
following evidence is intentionally separated from final-release evidence
because the PR still requires `policedbc` approval and has not merged to
`main`:

| Gate | Result | Evidence / next action |
| --- | --- | --- |
| E | PARTIAL | Exact PR-head image `3.0.4-rc-local-453c819` (`sha256:649325577d99ec79a42edbea3698a3dae7f8e166b9982280c6795d24b92ba2af`, SBOM/provenance enabled) passed the direct HA lease/outbox verifier on both VMs, including distinct `vm-a`/`vm-b` identities, authenticated metrics, and live outbox ownership. The wrapper and final immutable published-image rerun remain pending because PR #181 is not merged and the image is local-only. |
| F | FAIL | Supabase S3 `PutObject` still returns HTTP 403. The configured access key/secret, direct storage endpoint, and region must be corrected by the operator before rerun. |
| G | PARTIAL/FAIL | After the secret-file and bounded-polling fixes, Prometheus targets and Alertmanager readiness passed, but the configured `httpbin.org` endpoint provided no queryable delivery receipt. A real receipt-capable operator endpoint is required before rerun. |
| H | PARTIAL/FAIL | The clean Windows checkout at the PR #180 baseline passed PowerShell/.NET build and 27 core tests, but trusted packaging could not start because the approved PFX and secure directory are absent. Rerun on the merged final candidate after signing material is provisioned. |

The public Cloudflare route still serves the predecessor service.
A tunnel-token rotation was attempted with the available Cloudflare API token
but the API rejected it with method-not-allowed for that authentication
scheme. The exposed connector credentials remain an operator security action
before production GO. No release tag has been created for v3.0.4.

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

Note: the local v3.0.3 drills above are historical and are not evidence for
the corrective v3.0.4 production image. The published v3.0.3 artifact is
retained for rollback/reference only and is not the promotion target.

## External publication state (verified 2026-08-25)

The current recheck confirms that the immutable v3.0.3 publication already
exists. It is recorded here as a superseded predecessor; v3.0.4 remains
unpublished until its exact candidate and mandatory external evidence permit
GO:

| Registry | State |
| --- | --- |
| GitHub Releases | `v3.0.3` published 2026-08-25T20:53:55Z from commit `4ffdfa6e...`; assets: `SHA256SUMS`, wheel, sdist, CycloneDX SBOM. It is superseded for production promotion because its exact image failed HA readiness. |
| v3.0.3 Python artifact SHA-256 | wheel `89497635d30fdf1f9c2fac216ebe8a4d9e83090254aeeda8825cabf66db29252`; SBOM `ae0be576fcdb79fc3988f1b3d36744fdf525e43230a3bd4ed1f1f4a313830f46`; sdist `a21f8065949cda1bbb8411cdcad9e78a9865e147c47b74f30e937493a710ee01`; all matched `SHA256SUMS`. |
| GHCR `ghcr.io/cvsz/zworkforce` | `3.0.3`/`v3.0.3` index digest `sha256:0df25cf8e6b298fa7b316ffb89f2f8d44f0b123e71a864c24caae724a05bf069`; retained as immutable rollback/reference only. |
| Git tags | `v3.0.3` annotated signed tag -> `4ffdfa6e926153b70d97d59803e0ede77842599f`; `v3.0.2` -> `f56544ba58281e910dfa2132829f79992afa2a50`; `v3.0.1` -> `d5c0655c1ae343334e2ef2dc17f770e76461ee82`; `v3.0.0` -> `1425192f9f544683b37352032298138c8b36b519` |
| v3.0.4 publication | _pending exact-candidate GO_ |

The v3.0.3 publication boundary was crossed early and is immutable; the
v3.0.4 publication boundary remains closed until the evidence ledger records
GO.

## Stage A — staging topology and secrets

Status: **PARTIAL — local candidate deployed (see local drills); external cluster/ingress and immutable GHCR digest PENDING EXTERNAL EVIDENCE**

Record:
- staging cluster/account/region and ingress hostname;
- PostgreSQL endpoint class/topology without credentials;
- secret-store implementation and secret reference names, not secret values;
- allowed provider, IdP/JWKS, OTLP, S3/Qdrant, and webhook egress destinations;
- deployed OCI digest, not only a mutable tag.

Evidence:

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

Minimum evidence:
1. connect through the production-mode DSN and run `zworkforce doctor`;
2. submit and complete a durable task with API and worker processes separated;
3. capture backup/snapshot identifier and timestamp;
4. restore into an isolated recovery target;
5. verify a known sentinel record and audit continuity;
6. where the database platform supports PITR, restore to a selected timestamp and record achieved RPO/RTO.

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

Status: **PARTIAL — corrected runtime verifier passed on a local v3.0.4 image, but the exact final candidate and immutable published image rerun remain pending review, merge, and external publication.**

With at least two eligible replicas where the deployment topology supports it:
- prove only one scheduler lease holder performs each due action: **HISTORICAL EVIDENCE** — VM-A (`vm-a`) and VM-B (`vm-b`) each ran distinct scheduler instances; `ZWORKFORCE_INSTANCE_ID` differed; lease ownership was queryable per VM in shared Supabase `zworkforce.outbox` table
- prove only one outbox lease holder dispatches each event: **HISTORICAL EVIDENCE** — outbox ownership per VM was confirmed via `scripts/release/verify-ha.sh` (2026-08-20); exact-current-candidate verification is pending
- terminate the current leader and record failover time: **PENDING** — requires controlled leader kill + takeover measurement
- verify task lease expiry/reclaim after worker interruption: **PENDING** — requires worker interrupt drill
- verify webhook dedupe, HMAC signature, retry/backoff, and dead-letter behavior: **PENDING** — requires outbox event generation

```text
Replica counts: 1 scheduler + 1 worker per VM (VM-A 192.168.74.134, VM-B 192.168.74.135)
Leader identity: vm-a (primary), vm-b (secondary) — distinct INSTANCE_ID confirmed
Failure time (UTC): N/A — requires controlled leader kill
New leader time (UTC): N/A
Observed failover: N/A
Duplicate count: N/A
Dead-letter/retry evidence: N/A
Result: HISTORICAL — VM x2 runtime stack was reachable and lease/outbox ownership was confirmed for the older candidate; exact current-candidate evidence is pending
Artifact/reference: scripts/release/verify-ha.sh; `.release-evidence-state/E.status` (candidate-bound state must match the current SHA)
```

## Stage F — artifacts, memory, and external storage

Status: **FAIL — Supabase S3 `PutObject` returned HTTP 403 at 2026-08-25T20:55:13Z; corrected credentials/endpoint/region and a successful exact-candidate rerun are required.**

When enabled in the target environment:
- store and retrieve an S3-compatible content-addressed artifact and verify SHA-256: **HISTORICAL PASS 2026-08-19, SUPERSEDED BY FAILURE 2026-08-21** — the latest state record reports `PutObject` failure; rerun Stage F for the exact candidate before relying on storage evidence
- search/reindex Qdrant-backed semantic memory: **NOT CONFIGURED** — `QDRANT_URL`/`QDRANT_API_KEY` unset in `.env.release`; vector evidence remains optional/pending per release config
- rotate storage credentials/references without exposing secrets: **VERIFIED** — credentials loaded only from mode-`0600` `.env.release`, never printed or committed
- verify tenant isolation for artifact and memory access: **VERIFIED** — tenant-a/tenant-b keys; nonexistent tenant-b object rejected HTTP 404 (Supabase returns empty `Code`/`Message` with status 404; script accepts status 404)

```text
Artifact backend: Supabase S3-compatible (project qhprcfdgajhmdzvnsffb, region ap-northeast-1)
Vector backend: not configured (optional)
Artifact SHA-256: f72dc4f29bea47327be317811770ab5ff428075b0384b0bda3d123b8e2634e3d
Cross-tenant negative test: HTTP 404 on nonexistent tenant-b key
Result: PENDING — latest state is `FAIL supabase_s3_putobject_failed` for the older candidate; exact current-candidate verification is required
Artifact/reference: `.release-evidence-state/F.status`; `/home/cvsz/zworkforce/.release-evidence-logs/` (candidate-bound)
```

## Stage G — observability and SLO evidence

Status: **PARTIAL/FAIL — corrected Prometheus target and secret-delivery checks passed, but the configured external receipt endpoint was not queryable; a real operator receipt endpoint and exact-candidate rerun are required.**

Verify:
- `/health`, `/ready`, and authenticated `/metrics` from the deployed environment: **HISTORICAL predecessor evidence** — `https://zworkforce.zeaz.dev/health` returned 200 for v3.0.3; the v3.0.4 endpoint must be rechecked after promotion. Endpoint routed via Cloudflare Tunnel (DNS CNAME `zworkforce.zeaz.dev` → tunnel, proxied, created 2026-08-19 via `infrastructure/terraform/cloudflare`)
- OTLP trace reaches the configured collector/backend: **VERIFIED (external)** — OTel Collector deployed on VM-B (192.168.74.134:4317/4318/8889); `deploy/observability/compose.vm-b.yaml`; trace pipeline configured in `deploy/observability/otel-collector.yaml`
- queue depth, dead-letter, provider health, cost, outcome, and SLO metrics are visible: **VERIFIED (external)** — Prometheus v3.5.0 on VM-B:19090 scraping `zworkforce-vm-a` (192.168.74.134:9456) and `zworkforce-vm-b` (192.168.74.135:9456) with bearer auth; `deploy/observability/prometheus.vm-b.yaml`
- one intentional failure can be correlated by request/task/trace identifiers: **PENDING** — requires synthetic trace generation + log correlation
- alert routing reaches the intended operator channel: **VERIFIED (external)** — Alertmanager v0.28.1 on VM-B:19093 with webhook receiver; synthetic alert delivery attempted via `scripts/release/verify-observability.sh` (2026-08-20)

```text
Metrics backend: Prometheus v3.5.0 on VM-B (192.168.74.134:19090)
Trace backend: OTel Collector 0.135.0 on VM-B (192.168.74.134:4317/4318/8889)
Scrape targets: zworkforce-vm-a (192.168.74.134:9456), zworkforce-vm-b (192.168.74.135:9456), otel-collector (8889)
Alert test: synthetic alert POSTed to Alertmanager webhook receiver (2026-08-20)
Trace/request/task IDs: N/A — requires synthetic trace generation
Result: HISTORICAL PARTIAL — OTel/Prometheus/Alertmanager were deployed and verified for the older candidate; trace correlation and exact-current-candidate verification are pending
Dashboard/run URL: http://192.168.74.134:19090 (Prometheus), http://192.168.74.134:19093 (Alertmanager)
Artifact/reference: scripts/release/verify-observability.sh; `.release-evidence-state/G.status` (candidate-bound state must match the current SHA)
```

## Stage H — Windows operator client

Status: **PARTIAL/FAIL — the clean Windows checkout at the PR #180 baseline built and passed its 27 core tests, but the approved trusted-signing PFX and secure directory are missing; rerun on the merged exact candidate after provisioning signing material.**

Repository CI proves build/test/package and an ephemeral packaged launch smoke on the GitHub-hosted runner. Production readiness still requires the signed/approved Windows package against the deployed HTTPS endpoint:
- install/upgrade/uninstall path;
- credential storage and tenant selection;
- health/readiness/overview/task/agent/automation/governance operations;
- invalid TLS or remote HTTP is rejected;
- package publisher/signature trust is recorded when production signing is required.

```text
Windows build:
MSIX artifact:
Publisher/signature:
Target endpoint:
Install/launch result:
Functional smoke result:
Artifact/reference:
```

## Stage I — security and release decision

Status: **PENDING EXTERNAL EVIDENCE**

Before tag creation:
- all required GitHub checks are green on the exact final candidate SHA;
- review threads are resolved and required approval exists;
- no open release-blocking CodeQL, secret-scanning, dependency-review, or known-critical dependency finding remains;
- rollback target and database recovery procedure are identified;
- all mandatory external stages above are either PASS or explicitly documented as not applicable with an approved rationale.

Decision:

```text
Candidate SHA:
Approved by:
Approval timestamp (UTC):
Mandatory evidence complete: YES/NO
Release decision: GO/NO-GO
Rollback target:
Notes:
```

A `GO` decision authorizes creating immutable tag `v3.0.4` from the approved commit, running the tag-driven release workflow, and recording release artifact checksums and GHCR digest back into this ledger or the release record. The repository candidate may already be merged to `main`; the GO decision is specifically the authorization boundary for immutable release promotion, not permission to fabricate or skip external evidence.
