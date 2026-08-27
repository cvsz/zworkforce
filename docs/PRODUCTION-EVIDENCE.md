# Production Release Evidence — zWorkforce v3.0.4 corrective candidate (provisional)

`v3.0.3` is an immutable published predecessor. It was published before the external GO evidence was complete and its exact HA image verification exposed two production defects: the image omitted the S3 runtime extra and its HA healthcheck invoked `curl`, which is not installed in the image. It must not be retagged or treated as the production promotion target.

This ledger tracks the corrective `v3.0.4` line while preserving a strict boundary between repository-complete evidence and environment-complete production evidence.

**Rule:** an item remains `PENDING EXTERNAL EVIDENCE` until an operator records the real environment, timestamp, command or run URL, result, and durable artifact/reference. CI output, source code, image tags, and transient terminal observations do not substitute for a durable external run record when the gate explicitly requires environment evidence.

## Current operator database configuration — 2026-08-26

The zWorkforce release target remains Supabase project
`qhprcfdgajhmdzvnsffb`, using its TLS session pooler at
`aws-0-ap-northeast-1.pooler.supabase.com:5432`; the password is supplied only
through the operator secret boundary. The generic `.env.core` files currently
identify `dryflnsxhjuaamnzfrtu`, whose schema is incompatible with zWorkforce,
so they must not be used as the zWorkforce runtime DSN. VM-B currently has the
release project's schema; VM-A is still on a different project and must be
reconfigured and reverified after the database credential rotation. This is a
configuration finding, not external PASS evidence.

## Current public ingress verification — 2026-08-26

The repository and Terraform plan now declare `zwf-api.zeaz.dev` as an alias
for the same tunnel origin as `zwf.zeaz.dev`. A read-only public probe from the
operator host at this timestamp found no DNS answer for `zwf-api.zeaz.dev`,
while `zwf.zeaz.dev/health` and the legacy hostname still returned HTTP 200.
The alias has therefore not been provisioned or externally verified; this is a
pending Cloudflare change, not a production PASS.

## Production topology

The intended production topology remains:

```text
Cloudflare
   |
   +-- zwf.zeaz.dev
   +-- zwf-api.zeaz.dev
   |       |
   |       +-- HA/load-balancing
   |             |
   |             +-- ha-a.zeaz.dev -> VM-A (192.168.74.134)
   |             +-- ha-b.zeaz.dev -> VM-B (192.168.74.135)
   |
   +-- obs.zeaz.dev -> VM-B observability

VM-A                     VM-B
API                      API
scheduler-A              scheduler-B
worker-A                 worker-B
outbox-A                 outbox-B
                         OTel Collector
                         Prometheus
                         Alertmanager
       \                  /
        +---- Supabase ---+
             PostgreSQL
             Auth
             Storage
```

- VM-A and VM-B are independent zWorkforce runtime replicas.
- Supabase project `qhprcfdgajhmdzvnsffb` is the intended shared durable data plane, not an HTTP runtime replica.
- Observability runs on the VM-B side of the deployment topology.
- Provider, database, signing, storage, Cloudflare, and observability credentials remain operator-owned external inputs and must not be committed to this ledger.

## Candidate identity

| Field | Value |
| --- | --- |
| Candidate version | `3.0.4` corrective candidate (provisional) |
| Governing release authority | `v3.0.3` remains authoritative in `ROADMAP.md`, `planning/exec-planning-zwf.md`, and `planning/RELEASE-SCOPE-STATUS.md`; this ledger does not authorize a v3.0.4 release |
| Corrective code base | `f935a5f472b942f29cc83279f75ed14bae7c3761` — PR #181 merge commit containing the v3.0.4 production-image / HA verifier correction |
| Current `main` after forward work | `2182129723d1a856546c45274308e1da2873f5bb` — PR #185 merge; this is post-candidate drift and is not covered by the earlier `f935a5f…` release evidence |
| Final release candidate SHA | _PENDING — re-freeze an exact `main` SHA only after governing release authority explicitly transitions to v3.0.4_ |
| Release tag | _NOT AUTHORIZED_ |
| Corrective local image digest | `sha256:a6341d3c4e1a1fb502b5e60a64c38b094daaa7202da84e4221ba8c6cd1b39971` — local candidate metadata only; immutable GHCR publication pending |
| Corrective image tar digest | `sha256:c664fb3410e0dd30c9de118b84d7dc4eb8229e9d6ae54643f63175e7c91284bf` — operator-reported transfer artifact metadata; not a durable verifier run record |
| Python artifact checksums | _PENDING tag-driven release workflow_ |

Any merge after `f935a5f…`, including this evidence update itself, creates post-candidate drift. Before any immutable `v3.0.4` promotion, the resulting exact `main` SHA must be frozen and all required repository and external gates must be evaluated against that exact candidate.

## Repository gates for corrective base `f935a5f…`

These checks are evidence for the corrective base/tree only. They do not authorize a tag and do not cover later `main` drift.

| Gate | Verified evidence | Status |
| --- | --- | --- |
| Python 3.12 / 3.13 / 3.14 | CI run `32915901873` | PASS on corrective base |
| PostgreSQL integration | CI run `32915901873`, including PostgreSQL backup/restore regression | PASS on corrective base; not external PITR evidence |
| Documentation contract | CI run `32915901873` | PASS on corrective base |
| Release integrity | CI run `32915901873` | PASS on corrective base |
| Container build | CI run `32915901873` | PASS on corrective base |
| Security invariants | CI run `32915901873` | PASS on corrective base |
| Dependency review | PR #181 run `32915171140` on the merged tree | PASS for PR review |
| CodeQL | run `32915901862` | PASS on corrective base |
| Windows client | PR #181 Windows run `32915171143`, tree-equivalent to the merge commit | PASS for repository build/test/package; not trusted production signing |

The PR that updates this ledger must independently satisfy the current protected-branch checks and approval rules. A green evidence-document PR proves only that the repository accepts the documentation update; it does not retroactively validate a later final release candidate.

## Immutable predecessor publication state

| Registry | State |
| --- | --- |
| GitHub Releases | `v3.0.3` published 2026-08-25 from `4ffdfa6e926153b70d97d59803e0ede77842599f`; immutable predecessor / rollback reference only |
| GHCR | `3.0.3` / `v3.0.3` index digest `sha256:0df25cf8e6b298fa7b316ffb89f2f8d44f0b123e71a864c24caae724a05bf069` |
| v3.0.4 publication | PENDING exact-candidate GO |

The v3.0.3 publication boundary was crossed early and remains immutable. The v3.0.4 publication boundary remains closed.

## Corrective external-gate attempt — 2026-08-25 to 2026-08-26

The following observations are useful diagnostics but are not a production GO. Where no durable candidate-bound execution artifact was retained, the result is deliberately recorded as pending rather than promoted to final external evidence.

| Gate | Current result | Evidence boundary / next action |
| --- | --- | --- |
| E — HA runtime | PARTIAL / PENDING DURABLE EVIDENCE | Operator observations reported that both VMs ran the local `f935a5f…` image, exposed distinct `vm-a` / `vm-b` identities, authenticated metrics, current scheduler lease ownership, and outbox claim rows. No durable verifier output/run artifact containing operator, exact timestamp, command/run reference, and captured result is attached to the repository. Scheduler action exclusivity and outbox dispatch exclusivity are therefore still PENDING. Preserve a candidate-bound log/evidence bundle and rerun against the final frozen SHA. |
| F — external storage | BLOCKED | Latest Supabase S3 `PutObject` returned HTTP 403. The observed release configuration referenced `dryflnsxhjuaamnzfrtu.supabase.co/storage/v1/s3` while the intended release project is `qhprcfdgajhmdzvnsffb`. Operator must provide valid credentials, endpoint, and exact region for the intended project, then rerun. |
| G — observability | PARTIAL / FAIL | Prometheus targets were observed UP and Alertmanager was ready, but the configured `httpbin.org` receiver produced no queryable delivery receipt. Exact-candidate trace correlation and alert receipt remain incomplete. Use an operator-owned receipt-capable endpoint and retain the resulting evidence bundle. |
| H — Windows trusted package | BLOCKED | Clean checkout was synchronized to `f935a5f…`, but the Azure Artifact Signing account/profile/verified publisher and a matching signed MSIX evidence set are not provisioned. Provision the operator-owned signer, then rerun signature/install/live-endpoint smoke on the final frozen SHA. |

The public Cloudflare route still serves the predecessor service. This ledger does not authorize changing that route. No `v3.0.4` tag has been created.

## Stage A — staging topology and secrets

Status: **PARTIAL — repository topology exists; exact final-candidate deployment, immutable GHCR digest, and environment evidence are PENDING EXTERNAL EVIDENCE.**

Required durable evidence:
- staging / production account, region, and ingress hostname;
- exact deployed OCI digest;
- PostgreSQL endpoint class/topology without credentials;
- secret-store implementation and secret references, never secret values;
- allowed provider, IdP/JWKS, OTLP, S3/vector, and webhook egress destinations;
- rollout command or run URL and captured result.

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

Status: **PARTIAL — repository PostgreSQL backup/restore regression passes; managed/external production-mode smoke, PITR, and measured RPO/RTO remain PENDING.**

Historical local PG 17.11 drills recorded a successful dump/restore, sentinel verification, audit continuity, and local recovery timing. Those drills are regression evidence only and do not replace managed-database recovery evidence for the final candidate.

Mandatory final-candidate evidence must:
- connect through the production-mode DSN and run `zworkforce doctor` successfully against the target database;
- submit and complete a durable task with API and worker processes separated, proving the restored/target database is usable by the deployed topology;
- capture the managed backup/snapshot identifier and timestamp;
- restore into an isolated recovery target;
- verify a known sentinel record, schema state, and audit continuity after restore;
- where supported, perform point-in-time recovery to a selected timestamp and record achieved RPO/RTO;
- retain the exact candidate SHA/image digest, operator, UTC timestamps, commands/run URLs, captured outputs, and durable artifact references.

```text
Database platform:
Production-mode doctor result:
Separated API/worker durable task ID and result:
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

Status: **PARTIAL — local API-key create/use/scope-deny/revoke/post-revoke rejection is verified; production OIDC/JWKS positive and negative cases remain PENDING.**

Required final evidence:
- valid issuer/audience/JWKS authentication;
- invalid issuer, audience, expiry, and signature rejection;
- tenant/role/scope mapping;
- API-key rotation and revoke lifecycle;
- confirmation that bearer tokens/provider credentials are absent from browser/static assets and logs.

## Stage D — provider routing, failover, and bounded execution

Status: **PARTIAL — real NVIDIA NIM routing succeeded for Luna/Terra/Sol and local circuit behavior was exercised; exact-candidate production routing, bounded-execution safety, and external failure/fallback telemetry remain PENDING.**

Historical routing evidence used NVIDIA NIM and verified the configured Luna/Terra/Sol model mapping. A local `drill-bad` provider exercised bounded retries, circuit open, denial, and recovery through the healthy provider. Historical results are regression evidence only.

Mandatory final-candidate evidence must:
- verify Luna/Terra/Sol resolve to the intended production providers/models and complete successful requests in the frozen environment;
- inject or otherwise control a primary-provider failure and capture the expected circuit/fallback/recovery path with external telemetry;
- prove retry, timeout, iteration, and cost/token budgets remain bounded by the deployed configuration and do not permit unbounded execution;
- verify mutating tools remain deny-by-default and execute only with the required explicit grant/policy/approval authority;
- verify provider credentials remain server-side and are absent from browser/static assets, model-visible payloads where not required, logs, traces, and audit details;
- retain candidate-bound provider health/circuit metrics, task/request/trace identifiers, exact candidate SHA/image digest, operator, UTC timestamps, and durable run artifacts.

```text
Provider/model mapping:
Successful tier requests:
Failure injected:
Fallback/recovery observed:
Retry/timeout/iteration/cost bounds:
Mutation deny-by-default / approved mutation evidence:
Credential containment evidence:
Task/request/trace IDs:
Result:
Artifact/reference:
```

## Stage E — scheduler, worker, outbox, and HA leases

Status: **PARTIAL / PENDING DURABLE EVIDENCE — current external observations show two runtime identities, a current scheduler lease holder, and outbox claim presence, but they do not prove per-action scheduler exclusivity or per-event outbox dispatch exclusivity. No durable candidate-bound HA verifier output is attached.**

With at least two eligible replicas, final evidence must:
- prove only one scheduler performs each due action: **PENDING** — `scripts/release/verify-ha.sh` reads the current `service_leases3` lease but does not create a due schedule or assert occurrence/deduplication counts; run a candidate-bound dual-replica due-action drill and assert exactly one action per occurrence;
- prove outbox claim ownership: **OBSERVED, NOT FINAL EVIDENCE** — current rows were observed with a non-empty owner, but the retained repository sources do not include the external verifier output;
- prove only one outbox holder dispatches each event: **PENDING** — current verifier does not assert owner uniqueness over the event lifecycle, active claim expiry, delivery state, or per-event dispatch counts;
- terminate the current scheduler leader and measure takeover: **PENDING**;
- interrupt a worker and verify task lease expiry/reclaim: **PENDING**;
- generate webhook events and verify dedupe, HMAC, retry/backoff, and dead-letter behavior: **PENDING**;
- retain a durable run artifact containing exact candidate SHA/image digest, VM identities, UTC timestamps, operator, command/run URL, captured verifier output, and checksums: **PENDING**.

```text
Replica counts: 1 scheduler + 1 worker per VM
Current observed identities: vm-a, vm-b
Failure time (UTC): PENDING controlled drill
New leader time (UTC): PENDING
Observed failover: PENDING
Scheduler occurrence duplicate count: PENDING
Outbox per-event dispatch count: PENDING
Dead-letter/retry evidence: PENDING
Result: PENDING final Stage E evidence
Artifact/reference: source verifier and image digest are known; durable external run bundle is PENDING
```

## Stage F — artifacts, memory, and external storage

Status: **BLOCKED — Supabase S3 `PutObject` returned HTTP 403; correct project/endpoint/credentials are required before an exact-candidate rerun.**

Historical successful local/storage tests do not override the latest failed external write. Final evidence must include content-addressed write/read with SHA-256 verification and cross-tenant negative access on the intended production storage project.

```text
Artifact backend: Supabase S3-compatible — intended project qhprcfdgajhmdzvnsffb
Latest exact external write: BLOCKED / HTTP 403
Vector backend: optional / not configured in current release environment
Result: BLOCKED
Artifact/reference: operator must retain rerun output without secrets
```

## Stage G — observability and SLO evidence

Status: **PARTIAL / FAIL — current scrape targets and Alertmanager readiness were observed, but exact-candidate synthetic trace correlation and receipt-capable alert delivery are incomplete.**

Final evidence must include:
- `/health`, `/ready`, and authenticated `/metrics` on the deployed final candidate;
- OTLP trace receipt in the configured collector/backend;
- queue, dead-letter, provider health, cost, outcome, and SLO metrics;
- one intentional failure correlated by request/task/trace identifiers;
- alert routing to an operator-owned endpoint with a queryable delivery receipt;
- retained run output/checksums.

## Stage H — Windows operator client

Status: **BLOCKED — repository Windows CI passes build/test/package, but Azure Artifact Signing provisioning and live-endpoint installation/smoke evidence remain operator-owned prerequisites.**

Final evidence must record:
- exact candidate checkout;
- trusted MSIX publisher/signature;
- install/upgrade/uninstall path;
- secure credential storage and tenant selection;
- health/readiness/overview/task/agent/automation/governance smoke against the deployed HTTPS endpoint;
- rejection of invalid TLS / disallowed remote HTTP.

```text
Windows checkout: final frozen SHA PENDING
Azure Artifact Signing account/profile/verified publisher: operator provisioning PENDING
Pre-tag candidate signing workflow/run: PENDING
MSIX artifact:
Publisher/signature:
Timestamp:
SHA-256:
Target endpoint:
Install/launch result:
Functional smoke result:
Artifact/reference:
```

## Stage I — security and release decision

Status: **PENDING EXTERNAL EVIDENCE**

Before tag creation:
- governing release authority explicitly names v3.0.4 and the exact frozen candidate SHA;
- all required GitHub checks are green on that exact final candidate;
- review threads are resolved and the protected branch has the required independent approval;
- no open release-blocking CodeQL, dependency-review, secret, or known-critical dependency finding remains;
- rollback target and database recovery procedure are identified;
- mandatory external Stages A-H are PASS or explicitly marked not applicable with approved rationale;
- all external PASS claims have durable candidate-bound evidence, not only source-code references or transient observations.

Decision:

```text
Candidate SHA:
Approved by:
Approval timestamp (UTC):
Mandatory evidence complete: NO
Release decision: NO-GO
Rollback target: v3.0.3 immutable predecessor until a later approved target is recorded
Notes: v3.0.4 remains provisional; do not create the tag from a moving main branch.
```

A future `GO` authorizes creating immutable tag `v3.0.4` from the explicitly approved exact commit, running the tag-driven release workflow, and recording final artifact checksums and GHCR digest. Until that decision is recorded, merging documentation or forward-roadmap work does not authorize production promotion.
