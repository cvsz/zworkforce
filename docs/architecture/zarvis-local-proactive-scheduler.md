# Z.A.R.V.I.S. Local Proactive Scheduler Architecture

Epic: #148  
Issue: #155

## Flow

```text
Owner local policy
  -> allowlisted schedule
  -> independent proactive worker tick
  -> read-only loopback health adapter
  -> signal validation
  -> confidence / quiet-hours / budget / cooldown / dedup policy
  -> explainable local suggestion inbox
  -> optional approval handoff object
  -> no autonomous action execution
```

## Trust boundaries

The owner API and web console require `ZARVIS_LOCAL_OWNER_TOKEN`. The scheduler worker uses only `ZARVIS_PROACTIVE_WORKER_TOKEN`. Neither process receives the action worker token. The proactive service never calls an action execution endpoint.

The initial adapter accepts only an operator-configured, allowlisted loopback HTTP `/healthz` endpoint. It rejects redirects, credentials, queries, fragments, non-loopback hosts, alternate paths, and arbitrary URLs.

## Durable model

A single fixed journal `proactive-events.jsonl` stores versioned policy, subscription, evaluation, notification-decision, feedback, revocation, and handoff events. Reconstructed state is derived from the latest snapshots. Subscription IDs, notification IDs, targets, and source values never affect a filesystem path.

## Scheduling semantics

- intervals are bounded to 1–1440 minutes;
- owner timezone is a validated IANA zone;
- missed runs are either skipped or evaluated once;
- due work is serialized by the local server;
- every active subscription advances `next_run_at` after evaluation;
- restart recovery uses durable subscription snapshots.

## Notification policy

Server-side policy applies confidence threshold, quiet hours, daily delivered-notification budget, fingerprint deduplication, and cooldown. Suppressed decisions remain auditable and visible with a reason, but only `delivered` decisions count toward the daily budget.

## Approval handoff

An unhealthy signal may contain one narrowly scoped action proposal. Creating a handoff persists:

```json
{
  "destination": "zarvis-action-gateway",
  "requires_owner_approval": true,
  "executed": false
}
```

The handoff does not contact the action gateway, approve a preview, or execute a worker route. It is an owner-visible continuation object only.
