---
name: backend-architect
description: Design secure, modular backend services for Z Platform.
source:
  repository: cvsz/zeaz-platform
  path: apps/zai-factory/skills-vault/skills/backend-architect/SKILL.md
---

# Backend Architecture

## Dependency direction

```text
apps -> services -> packages/contracts
infra -> services
```

Applications do not access provider credentials, databases, wallet keys, or queue internals directly.

## Service ownership

- AI Gateway: provider routing, quotas, model policy, usage events.
- Agent Orchestrator: approval-gated job lifecycle and scoped tool grants.
- Billing Ledger: immutable usage-to-credit records only.
- Workspace Runtime: isolated execution and project storage.
- Identity: tenant, user, service identity and authorization.

## Design rules

1. Define contract before implementation.
2. One service owns each persisted entity.
3. Events must have IDs, idempotency keys, timestamps, tenant scope, and version.
4. Mutations require authorization and audit correlation.
5. Cross-service work uses APIs/events, never shared database tables.
6. Use timeouts, retry policy, and circuit breakers for every external dependency.
7. Do not make financial or infrastructure actions reachable from AI user routes.
