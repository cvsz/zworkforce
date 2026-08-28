---
name: comprehensive-review-full-review
description: Perform a release-grade review of a Z Platform migration or service change.
source:
  repository: cvsz/zeaz-platform
  path: apps/zai-factory/skills-vault/skills/comprehensive-review-full-review/SKILL.md
---

# Comprehensive Review

Review each migration batch against these gates.

## Correctness

- Contracts, request validation, error handling, and backward compatibility are explicit.
- Unit tests cover success, authorization, malformed input, timeout, and failure paths.
- Health endpoints do not require upstream connectivity.

## Security

- No credentials, production identifiers, wallet material, or payment data are committed.
- Browser code has no provider or service token.
- Agent tools are explicitly granted and approval-gated.
- Financial routes are unreachable from AI chat routes.

## Operations

- Service has health/readiness behavior, structured logs, correlation IDs, timeouts, and rollback notes.
- CI runs relevant tests and secret-pattern checks.
- Configuration is documented through non-secret example files.

## Review result

Classify each item as `pass`, `needs-change`, or `operator-decision`. Do not release when any critical item is not `pass`.
