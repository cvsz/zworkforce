# v3.0.4 Release-Scope Status Registry

**Updated:** 2026-08-29  
**Candidate line:** `v3.0.4`  
**Authority:** `ROADMAP.md`, `planning/exec-planning-zwf.md`, `docs/PRODUCTION-EVIDENCE.md`

This registry normalizes subsystem planning language for release triage without changing any subsystem's own Definition of Complete. Terms such as `Active`, `Production Target`, `Integrated`, or `Next Upgrade` inside feature plans describe product-roadmap state; they do not become current-release blockers unless the release authorities above explicitly bind them to `v3.0.3`.

## Allowed release-state vocabulary

| State | Meaning |
| --- | --- |
| `v3.0.4 required / complete` | Repository work explicitly required for the current candidate and implemented/verified to the evidence recorded by the release authorities. |
| `v3.0.4 required / incomplete` | A current candidate blocker that must be fixed before immutable promotion. |
| `forward roadmap` | Planned or active product work outside the current candidate boundary. Its own plan may remain incomplete. |
| `external evidence` | Operator-owned validation that cannot be inferred from repository implementation or CI. |

## Normalized subsystem classification

| Subsystem / plan | Normalized release state | Release interpretation |
| --- | --- | --- |
| zWorkforce control plane — `exec-planning-zwf.md` | `v3.0.4 required / complete` for repository candidate preparation; `external evidence` remains | Canonical current-release repository scope. Final immutable promotion still requires exact-candidate checks/reviews and all mandatory external evidence. |
| Z.A.R.V.I.S. — `exec-planning-zarvis.md` | `forward roadmap` | The plan explicitly identifies itself as the next Z.A.R.V.I.S. upgrade line. Existing v3.0.3 package/Windows obligations remain governed by current-release sources and CI. |
| Zeto — `exec-planning-zato.md` | `forward roadmap` | Targets the separate `cvsz/zeto` product line and retains its own incomplete product DoD; that incompleteness is not silently converted into a zWorkforce v3.0.3 blocker. |
| zsp-aitool — `exec-planning.zsp-aitool.md` | `forward roadmap` | Monorepo integration exists, while subsequent studio/tenant/render/affiliate milestones remain forward product work unless explicitly rebound to the current release. |
| Zider — `exec-planning.zider.md` | `forward roadmap` | Browser-companion feature roadmap continues independently; security/reliability fixes already merged into the candidate remain part of repository history, not evidence that the entire Zider plan is complete. |
| zknowbase native client — `docs/ZKNOWBASE-INTEGRATION.md` | `forward roadmap` | PR #166 adds an optional server-side read-only client boundary. Wiring it into governed agent/tool execution or tenant/policy-aware knowledge retrieval is follow-on feature work unless a current-release authority explicitly promotes it. |
| Security loop — `exec-zred-team.md` | continuous governance; actionable release findings become `v3.0.4 required / incomplete` | Continuous hardening is not a finite feature-completion flag. Any current critical/high actionable finding is a release blocker until resolved or explicitly accepted by policy. |
| Router — `exec-planning-router.md` | `forward roadmap` | Free-model routing, smart variants, gateway and observability expansion continue beyond the current release unless explicitly bound by release authorities. |
| Hermes / Spawn integration | `forward roadmap` plus `external evidence` for host/runtime proof | Repository integration does not imply external host installation or provider/runtime evidence. |
| Workspace-Agent / Skywork-inspired plan — `exec-planning-skywork.md` | `forward roadmap` | Delivered foundations may exist, but the active workspace upgrade plan remains forward scope unless a release authority promotes an item into the current candidate. |

## Current candidate blocker rule

A subsystem item becomes `v3.0.3 required / incomplete` only when at least one of the following is true:

1. `ROADMAP.md`, `planning/exec-planning-zwf.md`, or `docs/PRODUCTION-EVIDENCE.md` explicitly binds it to the current candidate;
2. a required exact-head GitHub check fails because of it;
3. an actionable release-blocking security/dependency finding identifies it;
4. an explicit master-plan requirement is declared current-release scope by the release authorities.

Otherwise, incomplete feature-plan work remains `forward roadmap` and must not be marked complete merely to make the candidate ledger green.

## External evidence boundary

The following remain `external evidence` until real operator-owned proof is recorded in `docs/PRODUCTION-EVIDENCE.md`: staging topology and immutable deployed OCI digest; managed PostgreSQL backup/restore/PITR and observed RPO/RTO; production identity and API-key lifecycle; configured provider failover; multi-replica scheduler/worker/outbox drills; external S3/Qdrant; OTLP/metrics/alerts; trusted Windows signing/live HTTPS; and the final approval, rollback target, and GO/NO-GO decision.

## Maintenance rule

When a plan is added or materially re-scoped, update this registry only after checking the current release authorities. Do not infer release-blocking status from words such as `Active`, `Target`, `Production`, or `Integrated` alone, and do not downgrade genuine current-release failures to `forward roadmap`.