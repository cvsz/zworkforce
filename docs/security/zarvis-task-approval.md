# Z.A.R.V.I.S. Task Approval Security Model

## Protected assets

- owner identity and approval intent;
- task objective, plan, inputs, checkpoints, and results;
- edge and worker credentials;
- GitHub and provider credentials;
- durable job, queue, and audit state.

## Threats and controls

| Threat | Control |
|---|---|
| Plan changed after user review | SHA-256 digest binds objective, ordered steps, dependencies, arguments, tools, and scopes |
| Approval replay | One-time nonce is cleared after approval and status transition prevents reuse |
| Stale approval | 15-minute expiry checked during approval and again before worker execution |
| Identity spoofing | Source invariant `github:4076926`; trusted-edge secret; caller identity ignored |
| Direct worker invocation | Independent `ZARVIS_TASK_WORKER_TOKEN` |
| Tool escalation | Closed read-only registry; grants derived from validated steps; mutating flag rejected |
| DAG injection/cycle | Dependencies may reference only earlier unique step IDs |
| Duplicate delivery | Tenant-scoped idempotency plus queue attempt deduplication |
| Request-controlled filesystem path | Fixed filenames only under operator-configured `AGENT_DATA_DIR` |
| Secret leakage | Secrets excluded from health, task snapshots, results, audit payloads, and browser code |
| Execution after pause | Paused jobs are not eligible for worker execution; resume re-enqueues safely |
| Execution after approval expiry | Worker returns `expired` before calling any tool |

## Trust boundaries

1. Identity-aware edge authenticates the exact owner.
2. Task gateway validates the plan and approval proof.
3. Agent lifecycle engine stores state and queues attempts.
4. Internal worker executes only approved read-only steps.
5. External GitHub input remains untrusted data and cannot alter policy or grants.

## Explicit exclusions

This slice does not permit repository writes, email sending, calendar mutation, desktop/browser control, financial activity, device control, offensive security actions, or autonomous mutation. Adding a tool requires a later typed capability and approval review; arbitrary tool names remain rejected.

## Emergency response

1. Disable the owner policy at the edge.
2. Rotate `ZARVIS_EDGE_SHARED_SECRET`.
3. Rotate `ZARVIS_TASK_WORKER_TOKEN`.
4. Stop the worker service.
5. Cancel non-terminal tasks.
6. Revoke downstream GitHub/provider tokens if compromise is suspected.
7. Preserve and review audit journals before restoration.
