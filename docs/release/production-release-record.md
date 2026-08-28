# Production Release Record

Status: `PENDING_OPERATOR`

## Candidate

| Field | Value |
|---|---|
| Repository | `cvsz/z-platform` |
| Full commit SHA | `<40-character-sha>` |
| Target environment | `production` |
| Change window | `<start/end ISO-8601>` |
| Staging evidence | `<artifact-reference>` |
| Evidence digest | `sha256:<digest>` |

## Immutable artifacts

| Workload | Approved image digest |
|---|---|
| Gateway | `<image@sha256:...>` |
| API | `<image@sha256:...>` |
| Worker | `<image@sha256:...>` |
| Web | `<image@sha256:...>` |

## Pre-flight

- Known risks: `<summary>`
- Success criteria: `<measurable criteria>`
- Abort criteria: `<measurable criteria>`
- Rollback trigger: `<conditions>`
- Rollback procedure: `<ordered steps or runbook reference>`
- Data migration/rollback constraints: `<details>`
- Monitoring dashboard and alert references: `<references>`

## Explicit decision

Decision: `<GO/NO-GO>`  
Production approver: `PHIPHAT PHOEMSUK` (CEO, ZeaZDev Company Limited; `seaza@msn.com`)
Approved commit SHA: `<40-character-sha>`  
Approved evidence digest: `sha256:<digest>`  
Approved at: `<ISO-8601>`  
Auditable approval reference: `<reference>`

A merge, successful CI run, or staging review is not a production GO decision.

## Operator record

The production release record also carries the operator-owned staging review context that must match the external readiness evidence for the same immutable release SHA:

| Field | Purpose |
|---|---|
| Staging reviewer | Named accountable reviewer for the external staging evidence |
| Incident owner | Primary operational owner during the release window |
| Escalation route | Tested path for paging and escalation during the change |
| Watch window | The post-release time window under active monitoring |

## Execution record

| Field | Value |
|---|---|
| Release operator | `PHIPHAT PHOEMSUK` (CEO, ZeaZDev Company Limited; `seaza@msn.com`) |
| Started at | `<ISO-8601>` |
| Completed at | `<ISO-8601>` |
| Deployed commit SHA | `<40-character-sha>` |
| Deployed image digests | `<reference>` |
| Deployment/GitOps record | `<reference>` |

The operator must stop if the deployed revision differs from the approved revision.

## Post-deploy

- [ ] Immediate health/readiness checks pass.
- [ ] Authentication and critical user journey pass.
- [ ] Provider connectivity passes.
- [ ] Logs, metrics, traces, and alerts are healthy.
- [ ] Audit export is visible.
- [ ] Error rate, latency, saturation, and queue depth remain within thresholds.
- [ ] Final outcome recorded as `DEPLOYED`, `ROLLED_BACK`, or `RELEASE_FAILED`.

## Abort protocol

When any abort criterion is met, halt rollout, notify incident ownership, execute the approved rollback plan, preserve evidence, and record the resulting state. Emergency deviations require an auditable authorization record.
