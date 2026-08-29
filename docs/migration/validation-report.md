# Migration Validation Report

## Prior branch head compose/start evidence (`3bc681f7a288b6a556d3885ee07623c8fb599b34`)

Date: 2026-07-16

| Gate | Result | Evidence |
|---|---|---|
| Scope | pass | One repository-local compose startup slice for the prior branch head `3bc681f7a288b6a556d3885ee07623c8fb599b34`. |
| Agent Control Panel startup | pass | `deploy/docker/next-service.Dockerfile` installs dependencies, builds the Next.js app, prunes dev dependencies, and starts the service without the missing `next` binary failure. |
| ZChat smoke alignment | pass | `scripts/staging-smoke.mjs` now checks the committed `<main class="shell">` markup and the current `@media (max-width: 720px)` breakpoint used by deployed checks. |
| Compose bring-up | pass | `DOCKER_CONFIG=/tmp/docker-config docker compose -f compose.yml up -d --build --wait` completed with all services healthy in isolated Compose. |
| Deployed smoke | pass | `node scripts/staging-smoke.mjs` completed successfully after the compose rebuild. |

This slice is repository-local and isolated Compose only. It does not replace GitHub Actions evidence or any operator-owned staging/production approval requirement, and it is not revalidated for the later fallback-label commit in this worktree.

## Current branch head repo-local validation (`d4b50605058786a800bcd9e8bfaa8d5def481424`)

Date: 2026-07-16

| Gate | Result | Evidence |
|---|---|---|
| Scope | pass | One repository-local branch-head validation slice only. |
| CodeQL workflow contract | pass | `node --test scripts/test/codeql-workflow.test.mjs` passed after the branch head was updated to `d4b50605058786a800bcd9e8bfaa8d5def481424`. |
| Secret/state hygiene | pass | `git add infrastructure/terraform/cloudflare/.gitignore infrastructure/terraform/cloudflare/terraform.tfstate infrastructure/terraform/cloudflare/terraform.tfstate.backup infrastructure/terraform/cloudflare/terraform.tfvars` followed by the pre-push hook removed tracked Cloudflare state files from the branch. |
| Repository-local validation | pass | `git diff --check` and `pnpm test` passed before the cleanup commit was pushed. |

This note binds the latest branch head to repository-local validation only. It does not claim any new GitHub Actions or external staging evidence.

## Release governance operator-signoff coverage

Date: 2026-07-16

| Gate | Result | Evidence |
|---|---|---|
| Scope | pass | One repository-local operator-signoff slice only. |
| Governance records | pass | `docs/operations/phase-6-operator-inputs.md`, `docs/release/operational-ownership.md`, and `docs/release/production-release-record.md` now explicitly bind the operator-owned approval path to the final release workflow. |
| Deterministic coverage | pass | `scripts/test/operator-governance.test.mjs` and `scripts/test/deployment-readiness-workflows.test.mjs` pass. |
| Template validation | pass | `node scripts/validate-release-templates.mjs` passed in this worktree. |

This slice is repository-local. It makes the remaining `PENDING_OPERATOR` items explicit and auditable, but it does not fabricate any reviewer, incident, or approval values.

## Supabase read-only Phase 6 API bridge

Date: 2026-07-16

| Gate | Result | Evidence |
|---|---|---|
| Scope | pass | One repository-local Supabase bridge slice only. |
| Auth boundary | pass | `/supabase/read` requires the existing Phase 6 bearer token and returns 401 without it. |
| Read-only data path | pass | The Phase 6 API reads a Supabase Data API table with `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_TABLE`; the anon key is not exposed to the browser. |
| Failure handling | pass | Missing config, invalid base URL, invalid table name, upstream 403, non-array payload, and out-of-range limit cases are covered deterministically. |
| Format and tests | pass | `python3 -m pytest services/phase6-api/tests/test_supabase_read.py services/phase6-api/tests/test_github_webhook.py`, `docker compose config --quiet`, and `git diff --check` passed in this worktree. |

This slice remains repository-local until an approved Supabase project and table are exercised as external evidence for the exact release candidate SHA.

## GitHub environment helper operator-field sync

Date: 2026-07-16

| Gate | Result | Evidence |
|---|---|---|
| Scope | pass | One repository-local environment-helper and docs-sync slice only. |
| Helper contract | pass | `scripts/configure-github-environments.sh` imports the staging review fields `STAGING_REVIEWER`, `INCIDENT_OWNER`, `ESCALATION_ROUTE`, `WATCH_WINDOW`, and the production reviewer selector fields from the loaded dotenv overlays. |
| Drift guard | pass | `scripts/test/configure-github-environments-script.test.mjs` and `scripts/test/current-head-evidence-sync.test.mjs` now assert the helper contract and the `origin/main` SHA used by the readiness docs. |
| Format and shell validation | pass | `bash -n scripts/configure-github-environments.sh` and `git diff --check` passed in this worktree. |

This slice is repository-local. It improves operator-readiness coverage and prevents the environment helper contract from silently drifting, but it does not claim external staging evidence or production approval.

## Production release record operator context

Date: 2026-07-16

| Gate | Result | Evidence |
|---|---|---|
| Scope | pass | One repository-local release-record contract slice only. |
| Template and schema coverage | pass | `production-release-record.yaml` and `schemas/release/production-release-record.schema.json` now require the operator-owned staging review context (`stagingReviewer`, `incidentOwner`, `escalationRoute`, `watchWindow`) alongside the approval and execution fields. |
| Deterministic coverage | pass | `scripts/test/operator-governance.test.mjs` now asserts the template and schema contract, and `node scripts/validate-release-templates.mjs` continues to validate the release-template set. |
| Format and workflow validation | pass | `git diff --check` and the focused Node test suite passed in this worktree. |

This slice is repository-local. It makes the production release record carry the same operator context that the external readiness harness already collects, but it does not fabricate the actual operator values.

## Identity-provider and tenant-claim decision record

Date: 2026-07-16

| Gate | Result | Evidence |
|---|---|---|
| Scope | pass | One repository-local identity/claim-mapping contract slice only. |
| Decision record validation | pass | `scripts/staging-decision-record.json` is now validated by `scripts/validate-staging-decision-record.mjs`, with `schemas/operations/staging-decision-record.schema.json` documenting the approved OIDC provider class and claim-mapping reference without exposing credentials. |
| Workflow coverage | pass | `.github/workflows/validate-release-evidence.yml` runs the new decision-record validator whenever the staging decision record changes. |
| Deterministic tests | pass | `scripts/test/staging-decision-record.test.mjs` and `scripts/test/deployment-readiness-workflows.test.mjs` cover the contract and workflow wiring. |
| Format and workflow validation | pass | `git diff --check` and the focused Node tests passed in this worktree. |

This slice is repository-local. It upgrades the identity-provider and tenant-claim mapping from placeholder prose to a validated operator decision record and a matching schema contract, but it still does not invent the actual external identity values.

## Phase 6 operator-input register

Date: 2026-07-16

| Gate | Result | Evidence |
|---|---|---|
| Scope | pass | One repository-local operator-input contract slice only. |
| Register coverage | pass | `scripts/phase-6-operator-inputs.json` now records the remaining Issue #1 `PENDING_OPERATOR` stack as a canonical machine-readable register, and `schemas/operations/phase-6-operator-inputs.schema.json` defines the expected shape. |
| Deterministic tests | pass | `scripts/test/phase-6-operator-inputs.test.mjs` and `scripts/test/deployment-readiness-workflows.test.mjs` cover the contract and workflow wiring. |
| Workflow validation | pass | `.github/workflows/validate-release-evidence.yml` now validates the operator-input register alongside the decision record. |
| Format and workflow validation | pass | `node --test scripts/test/phase-6-operator-inputs.test.mjs scripts/test/deployment-readiness-workflows.test.mjs` and `git diff --check` passed in this worktree. |

This slice is repository-local. It makes the remaining operator-owned stack auditable in machine-readable form, but it does not fabricate any secret-manager, billing, incident, or approval values.

## AI Gateway disconnect-aware upstream cancellation

Date: 2026-07-15

| Gate | Result | Evidence |
|---|---|---|
| Scope | pass | One repository-local AI Gateway slice only. |
| Disconnect handling | pass | The gateway aborts the upstream request when the client disconnects and does not retry after close. |
| Deterministic coverage | pass | Added a real-socket regression test for client disconnects plus existing startup-contract coverage. |
| Format, lint, typecheck, build | pass | `pnpm --dir services/ai-gateway test`, `pnpm test`, `pnpm lint`, `pnpm typecheck`, and `pnpm build` passed in this worktree. |
| Compose validation | pass | `docker compose config --quiet` and `docker compose build ai-gateway` passed in this worktree. |

This slice remains repository-local. It does not claim external staging, operator approval, or production readiness.

## Immutable release evidence binding

Date: 2026-07-15

| Gate | Result | Evidence |
|---|---|---|
| Scope | pass | One release-safety vertical slice only. |
| Backward compatibility | pass | Existing templates, schemas, services, and CLI contracts are unchanged. |
| Provider isolation | pass | No provider SDK or credential path added. |
| Unit coverage | pass by inspection; CI pending | Node tests cover exact, stale, malformed, placeholder, and missing evidence. |
| Format | CI pending | Changed JavaScript and JSON follow repository formatting conventions. |
| Lint | CI pending | No new dependency or lint suppression. |
| Typecheck | CI pending | Runtime is dependency-free JavaScript and does not modify typed packages. |
| Tests | CI pending | Root `pnpm test` includes `scripts/test/*.test.mjs`. |

The pull request is the authoritative source for CI results. Evidence must not be promoted to a release record until checks pass for the exact PR head commit.

## CodeQL Advanced workflow toolchain hardening

Date: 2026-07-16

| Gate | Result | Evidence |
|---|---|---|
| Scope | pass | One repository-local workflow-hardening slice only. |
| Toolchain setup | pass | `CodeQL Advanced` now provisions Node, pnpm, Go, and Python before `github/codeql-action/init@v4` on the available self-hosted Linux/X64 lane. |
| Deterministic coverage | pass | `scripts/test/codeql-workflow.test.mjs` asserts the runner labels, config binding, setup ordering, and `security-and-quality` query suite. |
| Format and workflow validation | pass | `python3` YAML parse of `.github/workflows/codeql.yml`, `node --test scripts/test/codeql-workflow.test.mjs`, and repo pre-push checks passed in this worktree. |

This slice is repository-local. PR-head CodeQL execution, alert-closure evidence, and immutable artifact binding still depend on GitHub Actions for the exact commit SHA.

## CI pnpm Node 24 alignment

Date: 2026-07-16

| Gate | Result | Evidence |
|---|---|---|
| Scope | pass | One repository-local workflow compatibility slice only. |
| Toolchain alignment | pass | `ci`, `validate`, and `CodeQL Advanced` now provision Node 24 before `pnpm install`, matching the pinned `pnpm@11.4.0` requirement. |
| Deterministic coverage | pass | `scripts/test/workflow-pnpm-setup.test.mjs` and `scripts/test/codeql-workflow.test.mjs` now assert the Node 24 setup step alongside the existing pnpm workflow checks. |
| Format and workflow validation | pass | `node --test scripts/test/workflow-pnpm-setup.test.mjs scripts/test/codeql-workflow.test.mjs` passed, and `CI=true pnpm install --ignore-scripts --store-dir /tmp/pnpm-store` completed in a clean worktree. |

This slice remains repository-local. It removes the Node 20 / pnpm 11 mismatch that caused `ERR_UNKNOWN_BUILTIN_MODULE: node:sqlite` during dependency installation, but it does not claim external staging, operator approval, or production readiness.
