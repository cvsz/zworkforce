---
name: api-design-principles
description: Design versioned, secure, maintainable REST and event APIs for Z Platform.
source:
  repository: cvsz/zeaz-platform
  path: apps/zai-factory/skills-vault/skills/api-design-principles/SKILL.md
  commit: 2fee2e1737e93daa42bf0808996186b630a7020f
---

# API Design Principles

Use this skill for Z Platform API contracts and API reviews.

## Required review

1. Identify consumer, tenant boundary, and authorization model.
2. Version public requests, responses, errors, and events.
3. Specify idempotency for mutating operations.
4. Define pagination, rate limits, timeouts, and retry behavior.
5. Validate inputs at the boundary and return stable error codes.
6. Include request and audit correlation IDs.
7. Provide contract tests before implementation.

## Platform constraints

- Browser clients never receive upstream provider credentials.
- Financial and wallet routes are isolated from AI and agent routes.
- Destructive and agent-mutating operations require an explicit approval state.
- Backward-incompatible public changes require a new versioned contract.
