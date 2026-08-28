---
name: framework-migration-code-migrate
description: Migrate legacy components into Z Platform incrementally and reversibly.
source:
  repository: cvsz/zeaz-platform
  path: apps/zai-factory/skills-vault/skills/framework-migration-code-migrate/SKILL.md
---

# Incremental Migration

## Required sequence

1. Inventory source files, dependencies, runtime ports, license, tests, and secrets.
2. Define target owner, contract version, compatibility boundary, and rollback point.
3. Import the smallest independently testable slice.
4. Add tests before switching a caller.
5. Run source and target validation.
6. Switch traffic/configuration only with explicit operator approval.
7. Keep a documented rollback path until stability evidence is collected.
8. Remove legacy code only after the agreed retention window.

## Prohibited actions

- Bulk-copying monorepo directories.
- Reusing legacy production hostnames, tokens, ports, or deployment identifiers.
- Combining code migration with production deployment.
- Removing a legacy path before target validation and rollback evidence.

## Evidence record

Every migration PR updates the migration manifest with source commit, target files, validation commands, outcome, and remaining risk.
