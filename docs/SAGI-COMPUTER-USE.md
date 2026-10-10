# SAGI Computer Use — Phase 1 Contract

**Status:** Experimental; stacked on SAGI PR #271. Not enabled in runtime.

The new `sagi_computer_use` module validates computer-use action *proposals*. It emits immutable metadata for observe/click/type/scroll/key, bound to tenant, actor, loop, plan digest, session, step, target and screenshot evidence SHA-256. It does not operate a computer, capture a screenshot, execute inputs, or authorize a session.

## Runtime integration design

1. Use an isolated ephemeral desktop/browser per tenant/job, not the operator's Windows session. Deny network egress by default, explicitly allow approved destinations; block localhost, metadata IPs, internal ranges and credential stores.
2. Use existing zWorkforce identity and a session-bound lease; enforce session expiry, resource caps and emergency stop.
3. Read-only screen observation requires scoped permission. Mutations (click/type/scroll/key) require canonical approval and policy checks over exact plan digest, action, target and fresh screenshot evidence. The request digest is only an audit/idempotency identifier, never an approval token.
4. Treat screenshots, accessibility trees, sites, documents and model outputs as untrusted. Disallow automatic credential entry, payments, deletion, browser security-setting changes, external posting and production mutation without explicit high-risk human approval.
5. Redact and minimize screenshots, mask sensitive fields, and implement TTL retention and tamper-evident audit metadata.
6. Execute with bounded tool schema, human-visible step previews, allowlisted actions and per-step independent verification; fail closed on stale screens, ambiguous selectors, navigation changes or unknown policy verdict.
7. Keep the runtime behind disabled-by-default feature flags and use existing agent-orchestrator/workspace-runtime approval and audit adapters; do not create a parallel identity or authorization service.

## Next deliverables

- Canonical session authority + isolated sandbox adapter with no implicit desktop access.
- Session/approval expiry and replay tests, network isolation tests, screen-state freshness checks.
- API and dashboard with approval requests and reversible stop control.
- Full CI/security and external production-equivalent evidence before rollout.

This feature is a computer-use **contract**, not a working remote desktop controller.
