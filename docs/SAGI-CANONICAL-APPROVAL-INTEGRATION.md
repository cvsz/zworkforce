# SAGI / Canonical Browser Effect Integration

This branch replaces the *design dependency* on standalone
`sagi_atomic_approval.AtomicApprovalStore` for mutation claims with an adapter
over the existing `Database.begin_browser_effect`,
`Database.claim_browser_effect` and `Database.finish_browser_effect`.

The canonical database enforces tenant task approval, distinct reviewers,
rejection/cancel checks, idempotency key and single transition to `executing`.
The adapter uses the complete SAGI action request digest as the effect
`action_sha256`. It has integration tests using repository-native stack.

**Security limitations, blocking production:**
- Approval task creation is still external to SAGI; callers must bind actual
  action target/plan/session/screen versions to the approved task, independently.
  A boolean approval or matching digest is not proof that the reviewer inspected
  the exact browser action.
- There is no worker lease token/fencing generation in `browser_effects3`.
  A stale worker finishing an already-claimed effect is not fenced.
- `executing`/ `unknown` effects remain unreplayed by design; reconcile
  ambiguous side effects manually, never blindly retry.
- Session validity, emergency stop, screenshot freshness and network isolation
  must be rechecked in the worker *after* effect claim and before any UI action.
- No real browser mutation is enabled here. Do not connect directly to public
  HTTP routes, production tasks or persistent browser sessions.

Next gate: canonical approval action binding + fencing-token migration,
network-enforced disposable worker, real E2E and verified audit evidence.
