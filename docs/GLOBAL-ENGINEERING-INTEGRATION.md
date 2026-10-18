# Global Engineering Skills and Agents Integration

Status: **Phase 1 — instructional integration only**. These files add skill contracts and operator guidance; they do **not** register executable agents, wire APIs, deploy workers, create scheduled jobs, or grant GitHub access. No production-readiness claim is made.

## Goal

Offer reusable investigation, architecture, implementation, security, QA, and release roles across personal, organization, and ZEAZDEV-internal installations without embedding ZEAZDEV credentials or bypassing the existing zWorkforce execution and approval model.

## Existing architecture and integration points

| Existing surface | Intended use | Status |
| --- | --- | --- |
| `zworkforce/skill_registry.py` | Verify trusted remotely distributed skills | Existing; no new registry registration |
| `services/agent-orchestrator/` | Durable authorized job lifecycle | Existing; no new job wiring |
| `services/workspace-runtime/` | Isolate untrusted code execution | Existing; no new worker allocation |
| zWorkforce tenant policy / RBAC / approval | Gate mutating actions | Existing; must be enforced by future adapters |
| `apps/agent-control-panel/` | Operator configuration / audit view | Future integration, not yet implemented |
| `.agents/skills/zeaz-global-engineering/` | Agent role orchestration contract | Added |
| `.agents/skills/zeaz-release-governance/` | Identity-agnostic release governance | Added |

## Runtime implementation plan

1. Define a validated tenant-scoped `EngineeringProfile` schema with repository allowlist, agent role mappings, provider installation references, execution limits, and release rules.
2. Implement a local-first installer connector that advertises capabilities without uploading source trees, shell history, credentials, or private files.
3. Register six role templates through existing agent template/version machinery, with read-only defaults and immutable pinned skill versions.
4. Bind each job to tenant, actor, repository, base SHA, target branch, scope, idempotency key, and bounded execution grant.
5. Produce durable audit events, test results, security findings, PR state, and evidence references. Keep secrets server-side.
6. Implement GitHub App-based read/PR operations with short-lived scoped installation tokens. Provide an opt-in local gh adapter for interactive development.
7. Require true independent reviewers, GitHub branch protection, exact-head checks, merge permission, and a separate authorized merge action. Deny by default when any gate is unknown.
8. Expose configuration and audit views in the existing operator panel only after backend authorization and tenant isolation tests pass.

## Profile example (non-secret)

```yaml
profile: personal
execution:
  mode: local
  auto_merge: false
  allow_production_deploy: false
github:
  provider: github
  reviewer_account: null
  merger_account: null
  repository_allowlist: []
  require_independent_review: true
  require_required_checks: true
```

For ZEAZDEV internal use, administrators can set `reviewer_account: policedbc` and `merger_account: cvsz` in an access-controlled deployment configuration. This is *not* evidence of review independence and does not override repository-level rules.

## Data minimization

Local mode requires no zWorkforce server account. Optional connected mode should retain pseudonymous agent/device ID, tenant/user ID, authorized repository installation reference, job and audit IDs, short-lived status metadata, and evidence pointers. Store credentials through approved secret mechanisms, not plaintext profile files. Source code remains local unless the operator explicitly authorizes transfer to a chosen processing destination. Support retention limits and revocation.

## Validation required before runtime release

- Schema parsing, invalid profile, and cross-tenant negative tests
- Permission-denied cases and impersonation resistance
- No credentials in browser bundles, logs, reports, or artifacts
- Crash/retry/replay-safe job behavior, idempotency, emergency stop
- Independent review, stale approval, changed head SHA, failed/pending required checks, and branch-protection negative tests
- Isolated worker execution and bounded networking
- Local offline installation/uninstallation and backward compatibility
- Exact-candidate checks plus release-specific external evidence under `docs/PRODUCTION-EVIDENCE.md`

Do not implement account switching as a global mutation of shared server credentials. Each worker/job must use its own scoped identity context.
