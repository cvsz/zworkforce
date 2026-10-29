# Agent and Skill Catalog Threat Model

## Assets
Tenant data, source code, provider credentials, tool permissions, job state, budgets, audit records, artifacts, and release credentials.

## Trust boundaries
User to orchestrator; agent to agent; model to tool; retrieval source to prompt; tenant to tenant; worker sandbox to host; CI artifact to release; operator approval to production action.

## Threats and controls
| Threat | Required control |
|---|---|
| Prompt injection in retrieved content | Treat content as untrusted; authorize tools outside the model |
| Cross-tenant retrieval/memory leakage | Tenant-scoped filters and negative integration tests |
| Unauthorized side effects | Deny-by-default policy, scoped grants, human approval |
| Secret leakage | Server-side references, redaction, data minimization |
| Replayed webhook/tool request | Signature validation, replay protection, idempotency |
| Runaway cost or loops | Budgets, max steps, timeouts, cancellation |
| Unsafe generated code | Isolated sandbox, resource limits, no host credentials |
| Supply-chain tampering | Pinned dependencies/actions, provenance, artifact integrity |
| Stale model facts | Maintained provider metadata and verification |
| False release confidence | Exact-head checks, immutable evidence, independent review |

Markdown instructions cannot enforce authorization, sandboxing, tenant isolation, rate limits, or audit integrity. These must be enforced in zWorkforce and verified through tests. This catalog is not a substitute for security assessment or external production verification.
