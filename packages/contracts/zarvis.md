# Z.A.R.V.I.S. Contracts

Versioned contracts for the Z.A.R.V.I.S. command, result, audit, durable session, task, approval, memory, privacy, perception, local action, and proactive boundaries.

## Schemas

- `schemas/zarvis.command.requested.v1.schema.json`
- `schemas/zarvis.command.completed.v1.schema.json`
- `schemas/zarvis.audit.tool-executed.v1.schema.json`
- `schemas/zarvis.session.event.v1.schema.json`
- `schemas/zarvis.task.requested.v1.schema.json`
- `schemas/zarvis.task.approval.v1.schema.json`
- `schemas/zarvis.task.snapshot.v1.schema.json`
- `schemas/zarvis.memory.proposal.v1.schema.json`
- `schemas/zarvis.memory.snapshot.v1.schema.json`
- `schemas/zarvis.memory.export.v1.schema.json`
- `schemas/zarvis.action.preview.v1.schema.json`
- `schemas/zarvis.action.approval.v1.schema.json`
- `schemas/zarvis.action.result.v1.schema.json`
- `schemas/zarvis.action.rollback.v1.schema.json`
- `schemas/zarvis.proactive.policy.v1.schema.json`
- `schemas/zarvis.proactive.subscription.v1.schema.json`
- `schemas/zarvis.proactive.signal.v1.schema.json`
- `schemas/zarvis.proactive.notification.v1.schema.json`
- `schemas/zarvis.proactive.feedback.v1.schema.json`
- `schemas/zarvis.proactive.action-handoff.v1.schema.json`

## Command and session rules

- Clients submit transcripts, never provider, GitHub, edge, or service credentials.
- `github.repository.status` remains the only synchronous command tool and is strictly read-only.
- A client-supplied `command_id` is the command idempotency key.
- Reusing a `command_id` with identical content returns the stored response with `replayed: true`.
- Reusing a `command_id` with different content fails with `409 idempotency_conflict`.
- Session history is append-only and records accepted, completed, or failed command transitions.
- Tool execution emits a separate allowlisted audit event.
- Session deletion is an explicit owner privacy action and requires a matching confirmation value.

## Durable task rules

- Task identity is permanently `github:4076926` in tenant `owner-4076926`.
- Task steps form an ordered DAG; dependencies may reference only earlier unique step IDs.
- The task registry admits only `github.repository.status` and `zarvis.repository.summary` in this slice.
- Every task step is read-only; a `mutating: true` request fails closed.
- `idempotency_key` may replay only the identical canonical plan.
- Approval requires the exact SHA-256 plan digest and one-time nonce before expiry.
- The worker checks approval expiry again before any tool call.
- Pause, resume, cancel, retry, checkpoint, and terminal state transitions are versioned and audited.

## Memory and privacy rules

- Memory identity is permanently `github:4076926` in tenant `owner-4076926`.
- A proposal is not retrievable memory and cannot affect assistant behavior before confirmation.
- Proposal approval binds content, classification, reason, confidence, retention, expiry, provenance, memory ID, and revision.
- Corrections create a higher revision through the same proposal and confirmation path.
- Working, episodic, semantic, and procedural memories have bounded classification-specific retention.
- Raw credentials, private keys, tokens, passwords, and payment-card-like data are rejected.
- Active memory snapshots always include provenance and owner identity.
- Export is versioned and contains active non-expired memories only.
- Delete physically compacts every encrypted proposal and revision for the memory; the local adapter has no persisted plaintext search derivative.
- Expired memories are excluded from retrieval immediately and physically purged by a separately authenticated worker.

## Local action rules

- Action identity is permanently `github:4076926` in tenant `owner-4076926`.
- `sandbox.preference.set` is the only registered capability and has no external side effect.
- Every mutation requires an impact preview containing the exact previous and next values.
- Approval is bound to the action ID, capability, key, values, owner, tenant, and expiry by SHA-256 digest and one-time nonce.
- The local worker has an independent token, never receives the owner token, and can list only approved action IDs.
- Execution uses compare-and-set; state drift fails closed without mutation.
- Successful execution emits an execution-bound rollback digest and nonce.
- Rollback uses compare-and-set again and restores or deletes the previous preference value.
- Emergency stop persists before revoking every pending or approved action.
- Request-controlled values never determine filesystem paths.

## Proactive intelligence rules

- Policy, subscription, notification, feedback, and handoff identity is permanently `github:4076926` in tenant `owner-4076926`.
- The initial scheduler admits only `local.service.health` for the allowlisted `zarvis-action-gateway` loopback target.
- Arbitrary URLs, non-loopback hosts, credentials, queries, fragments, redirects, and alternate paths are rejected.
- Quiet hours, daily delivered-notification budget, confidence threshold, cooldown, and fingerprint deduplication are enforced server-side.
- Missed runs are explicitly `skip` or `run_once`; restart recovery uses durable `next_run_at` and last-signal snapshots.
- Every evaluation, suppression, delivery, feedback, revocation, and handoff is append-only audited.
- Suppressed decisions remain explainable and do not count as delivered budget.
- External or untrusted content cannot create policy, schedules, subscriptions, or grants.
- An action handoff is a data object only. It fixes `requires_owner_approval: true` and `executed: false` and cannot call the action gateway.
- The proactive worker has an independent token and no owner or action credential.

Additional mutating capabilities cannot be enabled by reinterpreting command, task, memory, perception, action, or proactive schemas. Each capability requires a new narrow contract, threat model, tests, and owner-visible impact preview.
