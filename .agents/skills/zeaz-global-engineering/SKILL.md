---
name: zeaz-global-engineering
description: Orchestrates repository investigation, architecture, implementation, security review, QA, and governed release.
version: 1.0.0
---
# ZEAZ Global Engineering Workflow

Use the specialist roles as a coordinated workflow, not as a privileged runtime.

## Sequence
1. Investigator: read repository instructions, inspect current state, reproduce the issue, and record evidence.
2. Architect: propose the smallest compatible change, including migration, security, and operational risks.
3. Implementer: patch in an isolated workspace and add regression tests.
4. Security reviewer: assess AuthN/AuthZ, tenant boundaries, injection, secrets, dependencies, and supply chain.
5. QA engineer: run repository-native lint, type checks, tests, builds, and required integration checks.
6. Release manager: verify exact-head CI, independent review, branch rules, provenance, rollback, and evidence.

## Execution boundaries
- Read root and nearest nested agent instructions before changes.
- Use Thai for user-facing explanations and English for source, configuration, technical documentation, commits, and PR descriptions.
- Read-only discovery may proceed when tenant policy permits; mutations require a scoped authorization grant.
- Production deployment, credentials, infrastructure, destructive operations, and protected-branch mutation require separate operator approval.
- Run untrusted repository scripts only in an isolated, constrained worker.
- Record job/tenant/repository IDs, base/head SHAs, checks, reviewer decision, and immutable evidence references; redact secrets.
- Stop and report BLOCKED if authorization, independent review, exact-head CI, or external evidence is missing.

Workflow: Discover -> Reproduce -> Plan -> Authorized Patch -> Validate -> Security Review -> PR -> Independent Review -> Protected Merge -> Release Evidence.

This skill does not create a scheduler, grant permissions, approve or merge a PR, or claim production readiness.
