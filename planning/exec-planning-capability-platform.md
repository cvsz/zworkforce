# Execution Plan — Enterprise Capability Platform

**Repository:** `cvsz/zworkforce`  
**Track:** forward architecture / post-current-release capability platform  
**Companion architecture:** `../docs/ENTERPRISE-CAPABILITY-PLATFORM.md`

## 1. Objective

Evolve the existing zWorkforce skill/agent/workflow/MCP stack into one governed enterprise capability platform while preserving existing runtime invariants:

- tenant isolation;
- server-side secret containment;
- bounded execution;
- explicit authorization for mutations;
- durable state transitions;
- deterministic idempotency and replay protection where side effects exist;
- audit/provenance evidence;
- no duplicate assistant, workflow, policy, or approval stack.

The target capability kinds are Prompt, Skill, Agent, MCPServer, Workflow, KnowledgePack, EvaluationPack, PolicyPack, and Automation.

## 2. Delivery rules

1. One bounded vertical slice per PR.
2. Preserve backward compatibility unless the PR explicitly carries migration evidence.
3. New capability authority is deny-by-default.
4. Signing is necessary but not sufficient for runtime admission.
5. Models never become policy decision points.
6. Marketplace or remote content is untrusted until validated, evaluated, signed/trusted, and admitted by policy.
7. Every persistent resource is tenant-scoped unless explicitly defined as a global system artifact.
8. Current release evidence and forward roadmap evidence remain separate.
9. Prefer composition of existing modules over new services.
10. Production-readiness claims require executable evidence, not roadmap completion text.

## 3. Phase ECP-0 — Capability Contract Foundation

**Status:** implemented in the initial enterprise-capability-platform slice.

### Deliverables

- universal `zworkforce.ai/v1` capability manifest validator;
- recognized capability kinds;
- explicit owner/visibility metadata;
- explicit tools/scopes/secrets permission envelope;
- explicit read-only/mutating declaration;
- risk tiers R0-R5;
- approval quorum contract;
- explicit network mode and exact-host allowlist;
- bounded CPU/memory/timeout authority;
- provenance source and SHA-256 digest;
- optional evaluation suite threshold;
- deterministic capability fingerprint;
- backwards-compatible enterprise validation in `zworkforce/skills.py`;
- fail-closed enterprise skill update checks in the existing remote registry.

### Security acceptance criteria

- legacy ProMeta skills remain valid;
- enterprise skill manifests are signed over the complete governed envelope;
- `allowed_tools` cannot disagree with `permissions.tools`;
- mutating and R3-R5 capabilities require approval;
- remote enterprise updates cannot add tools, scopes, secrets, network access, mutation authority, or runtime resource authority;
- remote enterprise updates cannot weaken approval or silently lower declared risk;
- identity/kind/owner changes are rejected by the automatic upgrade path.

### Required validation

```bash
python -m compileall -q zworkforce tests
PYTHONPATH=. python -m unittest tests.test_capabilities -v
PYTHONPATH=. python -m unittest discover -s tests -v
zworkforce doctor
```

No release claim is made until repository CI passes the required branch-protection checks.

## 4. Phase ECP-1 — Persistent Universal Registry

### Goal

Promote capability metadata from a skill-only database concern into a first-class tenant-scoped registry without breaking current skill APIs.

### Data model

Introduce additive schema for concepts equivalent to:

```text
capabilities
capability_versions
capability_dependencies
capability_installations
capability_lifecycle_events
capability_trust_roots
capability_revocations
capability_evaluation_bindings
```

Minimum identity:

```text
tenant_id
capability_id
kind
version
manifest_digest
artifact_digest
publisher_id
created_at
```

### Lifecycle

Durable transitions:

```text
DRAFT
VALIDATED
SECURITY_SCANNED
EVALUATED
REVIEWED
SIGNED
PUBLISHED
APPROVED
PRODUCTION
DEPRECATED
REVOKED
```

Transitions are server-authorized operations, not writable manifest fields.

### Compatibility

- retain existing `skills2` reads during migration;
- use an additive backfill or compatibility adapter;
- keep SQLite/local and PostgreSQL behavior aligned where both are supported;
- run real PostgreSQL tests for schema/migration changes;
- no destructive migration without rollback evidence.

### Done when

- all capability kinds can be stored and versioned;
- tenant isolation negative tests exist;
- lifecycle transitions are policy-checked and audited;
- current skill registry consumers continue to work;
- migration/backfill is idempotent and restart-safe.

## 5. Phase ECP-2 — Discovery and Dependency Resolution

### Goal

Make capability discovery deterministic, permission-aware, and dependency-safe.

### Deliverables

- lexical metadata search;
- semantic discovery through existing retrieval primitives where appropriate;
- kind/owner/version/risk/visibility filters;
- tenant/policy pre-filtering before results are returned;
- dependency graph with cycle detection;
- exact-version or bounded-version resolution policy;
- revoked/deprecated package exclusion;
- deterministic resolver output with a resolution digest.

### Ranking inputs

Possible ranking inputs:

```text
relevance
quality/evaluation score
certification state
compatibility
historical success rate
freshness
organization preference
cost
risk
```

Ranking may recommend; policy still decides admission and execution.

### Done when

- two identical registry snapshots produce the same dependency resolution;
- unauthorized capabilities never appear in discovery results;
- cycles/conflicts fail closed;
- resolver decisions are auditable.

## 6. Phase ECP-3 — Execution Binding

### Goal

Bind a resolved capability version to existing task/workflow execution, policy, approval, telemetry, and audit state.

### Execution identity

Normalize correlation around:

```text
tenant_id
actor_id
task_id / execution_id
workflow_id
capability_id
capability_version
capability_digest
action_id
idempotency_key
policy_decision_id
approval_id
trace_id
```

### Rules

- capability resolution is frozen for an execution unless an explicit transition creates a new execution version;
- model output may request actions but never grants them;
- every mutating tool invocation is checked against both runtime grants and the frozen capability envelope;
- approval is bound to exact action intent/arguments/target/expiry where the underlying subsystem supports it;
- replay must not create duplicate committed side effects.

### Done when

- task/workflow evidence identifies exact capability versions;
- mid-run registry changes cannot silently change authority;
- mutation replay/idempotency tests pass;
- cancellation/retry behavior is deterministic.

## 7. Phase ECP-4 — MCP Registry and Gateway Governance

### Goal

Treat MCP server registration, discovery, and execution as governed capability operations.

### Deliverables

- first-class MCPServer capability metadata;
- server trust state and publisher identity;
- endpoint/transport metadata;
- tool schema snapshots and digesting;
- tenant policy filtering of MCP tools;
- argument validation;
- approval for mutating/high-risk tools;
- SSRF/redirect/public-destination rules retained from existing network security boundaries;
- audit and telemetry correlation per call;
- revocation that blocks new calls without deleting historical evidence.

### Done when

- discovery alone cannot execute a tool;
- an MCP server cannot expand permissions by changing its advertised tool list during an existing execution;
- changed schemas are versioned/digested;
- revoked servers fail closed.

## 8. Phase ECP-5 — Sandbox, Secrets, and Workload Isolation

### Goal

Bind runtime resource and secret declarations to deterministic enforcement.

### Deliverables

- map capability CPU/memory/timeout envelope into existing process-sandbox limits;
- explicit filesystem/workspace grants;
- platform-mediated network access;
- secret references resolved server-side only after policy checks;
- short-lived/scoped credentials where provider/tool support exists;
- redaction rules for logs, traces, audit details, and artifacts;
- stronger isolation adapter design for container/gVisor/Kata/microVM tiers without making unsupported deployment claims.

### Done when

- declared resource ceilings are enforced, not merely documented;
- undeclared secret access fails closed;
- network policy negative tests cover private/link-local/metadata-style destinations where applicable;
- browser/model payloads never contain provider secrets.

## 9. Phase ECP-6 — Evaluation and Certification

### Goal

Make evaluation evidence a registry admission input.

### Evaluation dimensions

```text
functional correctness
regression
security/adversarial behavior
prompt-injection resistance
authorization/tool-confusion
latency
cost
reliability
sandbox behavior
provider fallback behavior
```

### Deliverables

- evaluation suite as first-class capability binding;
- immutable evaluation run evidence with capability digest;
- minimum-score gates;
- regression comparison by version;
- shadow/canary hooks where the execution path supports them;
- revocation/depromotion on failed certification policy.

### Done when

- a changed manifest digest invalidates stale certification evidence;
- admission cannot reuse evidence for a different artifact;
- evaluation results are tenant-aware and auditable.

## 10. Phase ECP-7 — Enterprise Governance and Private Marketplace

### Goal

Add organization-scale publishing and governance on top of the trusted registry.

### Deliverables

- organization/private marketplace views;
- publisher identities and trust roots;
- asymmetric signing roadmap and key rotation/revocation;
- organization approval policy;
- delegated curator/reviewer roles;
- capability visibility controls;
- license/attribution metadata;
- quotas and FinOps attribution by capability/version;
- audit export/SIEM integration using existing observability/audit boundaries;
- retention and regional/data-residency controls where deployment architecture supports them.

### Done when

- publication and execution are distinct permissions;
- organization policy can prohibit public marketplace content;
- publisher revocation prevents new admission while preserving evidence;
- usage/cost is attributable to exact capability versions.

## 11. Phase ECP-8 — HA, DR, and Production Certification

### Goal

Prove the capability platform survives real operational failure modes.

### Required evidence

- multi-instance concurrency tests;
- PostgreSQL failover/recovery behavior where deployed;
- migration rollback/restore drills;
- registry backup and point-in-time restore procedure;
- lifecycle/outbox replay tests;
- revoked-capability cache invalidation tests;
- load and soak tests for discovery and admission;
- chaos/failure-injection of provider, MCP, database, and worker boundaries;
- audit completeness under partial failures;
- release artifact/SBOM/provenance verification;
- operational runbooks, alerts, SLOs, and rollback triggers.

### Target SLO candidates

These are design targets until measured in the deployed environment:

| Signal | Candidate target |
| --- | ---: |
| control API availability | >= 99.95% |
| registry read availability | >= 99.99% |
| policy/admission decision p95 excluding remote dependencies | < 100 ms |
| committed capability-state loss | 0 |
| unauthorized mutation | 0 |
| provider secret exposure | 0 |

## 12. Pull-request slicing recommendation

Recommended PR order after ECP-0:

1. **ECP-1A** — schema + migrations + persistence adapter;
2. **ECP-1B** — lifecycle state machine + audit;
3. **ECP-1C** — legacy skill backfill/compatibility;
4. **ECP-2A** — deterministic discovery/filtering;
5. **ECP-2B** — dependency resolver;
6. **ECP-3A** — frozen capability binding on task/workflow runs;
7. **ECP-3B** — policy/approval/idempotency correlation;
8. **ECP-4** — MCP capability governance;
9. **ECP-5** — resource/secret enforcement;
10. **ECP-6** — evaluation certification;
11. **ECP-7** — organization marketplace/governance;
12. **ECP-8** — HA/DR/certification evidence.

Each PR should remain independently rollbackable and should not bundle unrelated release bookkeeping.

## 13. Global Definition of Done

A capability-platform slice is complete only when applicable items below are evidenced:

- [ ] schema/API contract defined;
- [ ] backward compatibility assessed;
- [ ] tenant-isolation positive and negative tests;
- [ ] policy/approval behavior tested;
- [ ] idempotency/replay behavior tested for mutations;
- [ ] secret containment tested;
- [ ] audit/provenance evidence emitted;
- [ ] telemetry correlation present;
- [ ] focused unit tests pass;
- [ ] full local test suite passes;
- [ ] PostgreSQL integration tests pass for persistence changes;
- [ ] documentation links resolve;
- [ ] required GitHub branch-protection checks pass;
- [ ] rollback path is documented and tested where state/schema changes exist;
- [ ] production-evidence ledger is changed only when the release process explicitly promotes the slice.
