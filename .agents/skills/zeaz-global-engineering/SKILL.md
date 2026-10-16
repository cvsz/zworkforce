---
name: zeaz-global-engineering
description: Governed multi-agent investigation, implementation, security, QA, and release planning for repositories using zWorkforce. Use when onboarding global coding agents or executing a repository hardening workflow.
---

# ZEAZ Global Engineering Workflow

This skill is an orchestration contract, not a new privileged runtime. Use zWorkforce's existing tenant-scoped agents, durable jobs, policy engine, approval gates, and audit facilities. Never imply that a model instruction alone authorizes mutation.

## Specialist roles

1. Investigator: read instructions, inventory affected components, reproduce issues, and document evidence.
2. Architect: propose the smallest compatible design and identify migration, data, and operational risks.
3. Implementer: make scoped changes in an isolated worktree/sandbox with regression tests.
4. Security reviewer: examine auth, tenant boundaries, injection, secret exposure, dependencies, and supply chain.
5. QA engineer: execute repo-native lint, typecheck, tests, build, and pertinent integration checks.
6. Release manager: verify the exact PR head SHA, approval independence, branch protection, check conclusions, and rollback/evidence readiness.

## Execution boundaries

- Inspect root and nearest nested AGENTS.md before changes.
- Keep human-facing explanations in Thai; source code, configuration, code comments, documentation, commit subjects, and PR descriptions in English.
- Read-only discovery may run without release approval when tenant policy permits.
- Write operations require explicit authorized task scopes and existing zWorkforce execution grants.
- Production deployment, credentials, infrastructure, destructive operations, and protected-branch mutation require separate operator approval.
- Do not run untrusted repository scripts on the control-plane host; use an isolated constrained worker.
- Never claim zero warnings, full coverage, or production readiness without recorded evidence.
- Record job ID, tenant ID, repository, base/head SHAs, checks, reviewer decision, and immutable evidence references; redact secrets.
- Preserve the existing zWorkforce gates; this skill does not create a second scheduler, auth system, or approval authority.

## Workflow

Discover -> Reproduce -> Plan -> Authorized Patch -> Validate -> Security Review -> PR -> Independent Review -> Protected Merge -> Release Evidence.

Stop and surface a BLOCKED status whenever exact-head CI, review independence, policy authorization, or external evidence is unavailable.

## References

- `docs/GLOBAL-ENGINEERING-INTEGRATION.md`
- `docs/CENTER-CONTROL-PLANE.md`
- `docs/PRODUCTION-EVIDENCE.md`
- `.agents/skills/zworkforce-repo-review/SKILL.md`
