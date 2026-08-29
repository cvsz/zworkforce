# ADR-001: Repository Boundaries

## Status

Accepted

## Context

The repository must maintain clear boundaries between user-facing applications, deployable services, shared packages, and infrastructure. Without explicit boundaries, code drifts across layers, creating coupling, security gaps, and maintenance burden.

## Decision

Preserve the canonical top-level structure:

```text
z-platform/
├── apps/        # Thin user-facing products and BFFs
├── services/    # Independently deployable APIs and workers
├── packages/    # Shared libraries and versioned contracts
├── tools/       # Developer tooling and generators
├── scripts/     # Validation, CI, smoke, and release scripts
├── deploy/      # Dockerfiles and container assets
├── docs/        # Architecture, operations, security, migration
├── tests/       # Root-level integration tests
├── workers/     # Cloudflare Workers
└── .github/     # CI workflows and templates
```

Apps must not own:
- Reusable infrastructure clients
- Provider credentials
- General-purpose queues
- Execution engines
- Billing ledgers
- Shared schema definitions
- Duplicated platform authentication logic

Services must enforce dependency direction:
```text
API → Application → Domain ← Adapters/Infrastructure
```

Domain logic must not depend directly on vendor SDKs.

## Consequences

- Every feature has a canonical owner directory.
- New code has an obvious place to live.
- Architecture CI can enforce boundaries automatically.
- Security reviews can focus on service boundaries rather than searching the entire repo.
