# Universal Local Stack Intelligence — Execution Plan

Status: forward roadmap
Parent: planning/exec-planning.master.md
Review cadence: incremental ecosystem scan

## Objective

Continuously identify and safely evaluate open-source/local-first agents, skills, MCP servers, agent frameworks, developer tools, automation components and free/public model-provider integrations that materially improve zWorkforce.

## Phase U0 — Baseline and governance

- [x] Establish repository-local intelligence registry.
- [x] Separate upstream evidence from integration decisions.
- [x] Require license/cost/security/compatibility evidence.
- [x] Preserve zWorkforce as authority for policy, approvals, durable state, secrets and audit.

## Phase U1 — Runtime evaluation

### fast-agent

- [ ] Pin an exact upstream version after checking current release state.
- [ ] Run local and Docker coding benchmarks.
- [ ] Validate MCP and ACP interoperability.
- [ ] Validate cancellation, timeout and output limits.
- [ ] Compare resource usage with the current coding-agent path.

### AgentTeams

- [ ] Deploy a disposable local Kubernetes/Helm environment.
- [ ] Validate Team/Worker lifecycle and reconciliation.
- [ ] Validate MCP and provider authorization boundaries.
- [ ] Validate Matrix human-in-the-loop flow.
- [ ] Validate resource limits and observability.
- [ ] Test upgrade/rollback against the current deployment contract.

## Phase U2 — Research access

### Agent Reach

- [ ] Install in an isolated research worker.
- [ ] Run diagnostics and real command probes separately.
- [ ] Verify each enabled backend against real content retrieval.
- [ ] Record source provenance and collector version.
- [ ] Validate credential/cookie isolation.
- [ ] Validate fallback and rate-limit behavior.

## Phase U3 — Provider intelligence

For every newly discovered free/public provider:

- [ ] Verify official endpoint and exact quota/rate limits.
- [ ] Verify model/capability matrix and data policy.
- [ ] Verify tool-calling/structured-output support.
- [ ] Verify regional/auth constraints.
- [ ] Test through the existing model gateway.
- [ ] Add only if it creates measurable value.

## Definition of Done

1. Exact version pinned.
2. License/cost verified.
3. Local/self-host behavior verified.
4. Security boundaries tested.
5. Integration tests pass.
6. Failure/fallback behavior documented.
7. Observability/provenance exists.
8. Rollback/removal documented.
9. Owner and maintenance path recorded.
