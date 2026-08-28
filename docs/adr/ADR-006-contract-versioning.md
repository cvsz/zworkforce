# ADR-006: Contract Versioning

## Status

Accepted

## Context

Cross-boundary communication (REST, events, queue messages) must be versioned and backward compatible unless a migration strategy is documented. Without canonical contracts, services drift into implicit coupling.

## Decision

`packages/contracts` is authoritative for all cross-boundary schemas.

Naming convention:
- Events: `<domain>.<action>.<status>.v1` (e.g., `agent.job.requested.v1`, `billing.credit.created.v1`)
- REST requests/responses: `<service>/<resource>.<action>.v1` (e.g., `ai-gateway/chat.completions.request.v1`)
- Queue messages: `<service>.<queue>.<action>.v1`

Every cross-service contract must have:
- Version (semantic, starting at v1)
- JSON Schema validation
- Compatibility test
- Documented producer and consumer
- Migration strategy for breaking changes

Breaking contract changes require:
1. New version (e.g., v2)
2. v1 compatibility maintained during migration window
3. Producer and consumer updated independently
4. Deprecation notice in docs

## Consequences

- Producers and consumers can evolve independently within a version.
- CI validates that all schemas are valid JSON Schema Draft 7.
- Breaking changes are explicit and planned.
- New features have a clear place to define contracts.
