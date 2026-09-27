# Agent System Rules

## Language & Communication Guidelines
- **Primary Response Language:** Always communicate, explain, and write documentation/comments in **Thai** (ภาษาไทย).
- **Code & Configuration:** All source code, terminal commands, configuration files (JSON, YAML, ENV, etc.), variable names, and code syntax MUST remain in **English**.
- **Technical Terms:** Keep standard software architecture and programming jargon in English (e.g., *refactor*, *middleware*, *dependency injection*) to maintain accuracy.

## Response Behavior
1. **Explanations:** Provide all explanations, step-by-step guidance, and trade-off analyses in **Thai**.
2. **Code Blocks:** Write clean, executable code entirely in **English**. Do not translate programming keywords, variables, or API routes into Thai.
3. **Inline Comments:** Write comments within code blocks in **Thai** if they explain logic to the developer, but keep the code itself standard English.

## Repository Operating Rules
- Read this root `AGENTS.md`, `README.md`, contribution guidance, and repository-native configuration before making changes.
- If a nested `AGENTS.md` exists, treat the nearest file as the more specific instruction set for that subtree while preserving these root rules unless explicitly overridden.
- Preserve the existing architecture, public interfaces, naming conventions, formatting, and repository style unless the task explicitly requires a change.
- Prefer the smallest safe diff that fully solves the requested problem. Do not rewrite unrelated code or generated/vendor files.
- Never commit credentials, tokens, private keys, production secrets, personal data, or sensitive runtime output. Use documented secret/env mechanisms instead.
- Do not disable tests, security checks, type checks, lint rules, branch protections, or validation gates merely to make CI pass.
- Use repository-native build, test, lint, type-check, security, migration, and packaging commands whenever available.
- Before claiming a task complete, verify the relevant tests/checks and report what actually passed, what was not run, and any remaining blocker.

## Production Readiness
- Do not claim `production-ready`, `enterprise-ready`, `secure`, or `complete` without concrete evidence from the repository and validation results.
- For production-impacting changes, consider security, backward compatibility, observability, rollback, migrations, backup/restore, failure handling, and operational documentation.
- Treat authentication, authorization, payments, secrets, infrastructure, data migration, destructive operations, and externally visible API contracts as high-risk changes requiring extra validation.

## Git & Change Safety
- Do not force-push, rewrite shared history, delete unrelated branches/tags, or perform destructive Git operations unless the user explicitly authorizes that exact action.
- Keep commits focused and descriptive. Avoid mixing unrelated refactors with functional fixes.
- Do not merge failing changes or bypass required checks. If checks are unavailable, say so rather than assuming success.
- Preserve existing user work and project-specific instructions. When requirements conflict, follow the more specific repository rule or explicit user instruction and document the trade-off.

---

# Project-Specific Agent Rules

## Release status
Repository corrective candidate: `v3.0.4` (provisional).

The immutable `v3.0.3` tag was published 2026-08-25 (SHA `4ffdfa6`). `v3.0.4` is a corrective candidate addressing production-image and HA healthcheck defects exposed during `v3.0.3` external verification. **Do not create/tag `v3.0.4`** until:
1. Repository policy, exact-candidate checks/reviews are green on the frozen SHA
2. Mandatory external evidence in `docs/PRODUCTION-EVIDENCE.md` is recorded (Stages A–I)
3. Governing release authority explicitly transitions to `v3.0.4` and names the exact frozen candidate SHA
4. A GO decision is approved with rollback target (`v3.0.3`) identified

Forward feature plans under `planning/` (Z.A.R.V.I.S., Zeto, Zider, zsp-aitool, router, Hermes/Spawn, Skywork-inspired workspace) are **forward roadmap** — not `v3.0.4` release blockers unless explicitly bound by `ROADMAP.md`, `planning/exec-planning-zwf.md`, `docs/PRODUCTION-EVIDENCE.md`, a failing required check/security finding, or an explicit master-plan requirement.

Use `planning/RELEASE-SCOPE-STATUS.md` as the normalized subsystem classification overlay for release triage. It translates broad feature-plan labels (`Active`, `Production Target`, `Integrated`) into the four-state current-release vocabulary: `v3.0.4 required / complete`, `v3.0.4 required / incomplete`, `forward roadmap`, `external evidence`.

## Repository intent
zWorkforce is a production AI Workforce control plane. Changes must preserve tenant isolation, server-side secrets, bounded execution, explicit mutation authorization and durable state transitions.

## Required validation

```bash
python3 -m compileall -q zworkforce tests
PYTHONPATH=. python3 -m unittest discover -s tests -v
zworkforce doctor
```

PostgreSQL changes must also run `tests/test_v3_postgres.py` against a real PostgreSQL service. Runtime changes must not introduce `shell=True` or expose provider secrets in static assets.

## Architecture rules
- Browser/static code never receives provider/storage/database credentials.
- Durable state changes go through repository methods.
- Mutating tools stay deny-by-default and bounded.
- Preserve SQLite compatibility unless a change is explicitly PostgreSQL-only.
- Distributed queue code must be transactional and idempotent.
- Do not claim external infrastructure is provisioned merely because an adapter exists.

## Production evidence boundary (from `docs/PRODUCTION-EVIDENCE.md`)

External evidence remains **PENDING** for the `v3.0.4` corrective candidate:
- **Stage A** — Staging topology, immutable deployed OCI digest, environment evidence
- **Stage B** — Managed PostgreSQL backup/restore/PITR with observed RPO/RTO
- **Stage C** — Production OIDC/JWKS identity and API-key lifecycle (positive & negative cases)
- **Stage D** — Provider routing, failover, bounded execution, mutation deny-by-default
- **Stage E** — Scheduler/worker/outbox HA lease exclusivity, failure takeover, dead-letter
- **Stage F** — External S3 artifact write/read with SHA-256 verification (currently BLOCKED: HTTP 403)
- **Stage G** — OTLP trace correlation, alert receipt at operator-owned endpoint
- **Stage H** — Trusted Windows MSIX signing, live HTTPS operator install/smoke
- **Stage I** — Final GO decision: exact frozen SHA, required checks green, approvals, rollback target

**Rule:** An item remains `PENDING EXTERNAL EVIDENCE` until an operator records real environment, timestamp, command/run URL, result, and durable artifact/reference. CI output, source code, image tags, and transient terminal observations do not substitute for durable external run records when the gate explicitly requires environment evidence.

## External evidence gate
Do not claim external infrastructure (Supabase, Cloudflare, provider endpoints, Windows signing, etc.) is provisioned merely because Terraform/adapter/configuration exists. Credentials, accounts, controls, drills, and sign-offs must be recorded for the exact deployment in `docs/PRODUCTION-EVIDENCE.md`.

## Nested AGENTS.md
Subdirectory `AGENTS.md` files (e.g., `apps/zwallet/AGENTS.md`, `services/billing-ledger/AGENTS.md`) define binding rules for their respective boundaries. Root rules apply unless explicitly overridden. Read the nearest `AGENTS.md` before modifying any subtree.