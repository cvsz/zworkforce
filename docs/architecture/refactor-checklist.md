# Refactor Checklist

Machine-actionable backlog for the z-platform repository refactor.

Priority levels: P0 SECURITY/CORRECTNESS, P1 ARCHITECTURE, P2 RELIABILITY, P3 DEVEX, P4 CLEANUP.

---

## R0-001: Fix timing-unsafe auth in ai-gateway

- **ID:** R0-001
- **Domain:** Security
- **Problem:** `services/ai-gateway/index.js` uses `token !== process.env.Z_PLATFORM_SERVICE_TOKEN` for auth comparison, which is not timing-safe.
- **Evidence:** `services/ai-gateway/index.js:61`
- **Target:** Replace with `timingSafeEqual` comparison using `Buffer.from(token)` and `Buffer.from(expected)`.
- **Risk:** Low
- **Dependencies:** None
- **Files:** `services/ai-gateway/index.js`
- **Tests:** `services/ai-gateway/test/security-config.test.mjs`
- **Migration:** Update comparison; no API change.
- **Rollback:** Revert comparison.
- **Priority:** P0
- **Status:** PENDING

---

## R0-002: Fix service-to-service implementation import

- **ID:** R0-002
- **Domain:** Architecture
- **Problem:** `services/zarvis-task-gateway/server.mjs` imports `AgentOrchestratorError` from `../agent-orchestrator/server.mjs`, creating forbidden cross-service implementation dependency.
- **Evidence:** `services/zarvis-task-gateway/server.mjs:4`
- **Target:** Move shared error base class to `packages/errors` or define local `TaskError`.
- **Risk:** Low
- **Dependencies:** R1-001 (create `packages/errors`)
- **Files:** `services/zarvis-task-gateway/server.mjs`
- **Tests:** `services/zarvis-task-gateway/test/runtime.test.mjs`
- **Migration:** Update import path.
- **Rollback:** Revert import path.
- **Priority:** P1
- **Status:** PENDING

---

## R0-003: Standardize health endpoint shapes

- **ID:** R0-003
- **Domain:** Observability
- **Problem:** Health endpoints use inconsistent shapes and paths (`/health`, `/health/live`, `/healthz`, `/health/ready`).
- **Evidence:** 69 matches across repo for `/health` patterns.
- **Target:** Define standard `HealthResponse` schema in `packages/contracts`. Provide `/health` (liveness) and `/ready` (readiness) helpers in `packages/http-server`.
- **Risk:** Low
- **Dependencies:** R1-002 (create `packages/http-server`)
- **Files:** All services and apps
- **Tests:** Update smoke and readiness tests.
- **Migration:** One service at a time; keep backward-compatible paths during transition.
- **Rollback:** Revert per service.
- **Priority:** P2
- **Status:** PENDING

---

## R0-004: Standardize error response shapes

- **ID:** R0-004
- **Domain:** API
- **Problem:** Error responses use inconsistent shapes (`{ error: "..." }`, `{ error: { code, message } }`, `{ error: { message } }`).
- **Evidence:** 15+ custom error classes with different response serialization.
- **Target:** Standardize on `{ error: { code, message, request_id? } }` via shared response helper in `packages/http-server`.
- **Risk:** Low
- **Dependencies:** R1-002
- **Files:** All services and apps
- **Tests:** Update contract tests.
- **Migration:** Per service; maintain backward compatibility for external clients if needed.
- **Rollback:** Revert per service.
- **Priority:** P2
- **Status:** PENDING

---

## R0-005: Standardize security headers

- **ID:** R0-005
- **Domain:** Security
- **Problem:** Security headers are inconsistently applied. `ai-gateway` uses `helmet()`. `zvoice` and zarvis-* services define headers inline. Most services have no security headers.
- **Evidence:** Grep for `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options` shows inconsistent coverage.
- **Target:** Add shared security headers middleware in `packages/http-server`.
- **Risk:** Low
- **Dependencies:** R1-002
- **Files:** All services and apps
- **Tests:** Add header assertions to smoke tests.
- **Migration:** Per service.
- **Rollback:** Revert per service.
- **Priority:** P2
- **Status:** PENDING

---

## R0-006: Standardize body size limits

- **ID:** R0-006
- **Domain:** Reliability
- **Problem:** Body size limits vary from 32 KB to 8 MB with no consistent policy.
- **Evidence:** Grep for `MAX_BODY_BYTES` and `100000` shows 14+ different limits.
- **Target:** Define size limits per endpoint category (e.g., chat: 32 KB, admin: 64 KB, upload: 10 MB) in shared config.
- **Risk:** Low
- **Dependencies:** R1-003 (create `packages/config`)
- **Files:** All services and apps
- **Tests:** Update size-limit tests.
- **Migration:** Per service.
- **Rollback:** Revert per service.
- **Priority:** P2
- **Status:** PENDING

---

## R0-007: Consolidate Dockerfiles

- **ID:** R0-007
- **Domain:** Deployment
- **Problem:** Three Node Dockerfiles (`ai-gateway.Dockerfile`, `node-service.Dockerfile`, `next-service.Dockerfile`) with overlapping base patterns. Missing multi-stage builds, healthchecks, and `.dockerignore` in some.
- **Evidence:** `deploy/docker/`, `services/zc/Dockerfile`, `services/voice-*/Dockerfile`
- **Target:** Consolidate into parameterized `node-service.Dockerfile` with multi-stage, healthcheck, and `.dockerignore`. Replace `ai-gateway.Dockerfile` with generic build.
- **Risk:** Medium
- **Dependencies:** None
- **Files:** `deploy/docker/*`, `compose.yml`, `compose.*.yml`
- **Tests:** `docker compose build` in CI.
- **Migration:** Update Compose `dockerfile` references.
- **Rollback:** Revert Compose references.
- **Priority:** P2
- **Status:** PENDING

---

## R0-008: Consolidate Compose files

- **ID:** R0-008
- **Domain:** Deployment
- **Problem:** Six compose files with significant overlap.
- **Evidence:** `compose.yml`, `compose.voice.yml`, `compose.zarvis-local.yml`, `compose.zarvis-owner-domain.yml`, `compose.zarvis-owner-voice.yml`, `docker-compose.phase6.yml`
- **Target:** Consolidate into `compose.yaml` (base), `compose.dev.yaml`, `compose.test.yaml`, `compose.staging.yaml` using profiles.
- **Risk:** Medium
- **Dependencies:** R0-007
- **Files:** All compose files, `Makefile`, scripts
- **Tests:** `docker compose config --quiet`, `make setup`, `make start`
- **Migration:** Update Makefile and scripts to use new compose files.
- **Rollback:** Keep old files until all operators verify new topology.
- **Priority:** P3
- **Status:** PENDING

---

## R0-009: Create canonical config package

- **ID:** R0-009
- **Domain:** Configuration
- **Problem:** Environment variables are undocumented, inconsistently named, and lack type validation.
- **Evidence:** `docs/architecture/configuration.md` (inventory)
- **Target:** `packages/config` with typed schemas per domain (platform, ai, agent, workspace, billing, voice, zarvis). Fail closed on missing required config.
- **Risk:** Low
- **Dependencies:** None
- **Files:** `packages/config/`, `.env.example`
- **Tests:** Unit tests for schema validation.
- **Migration:** One service at a time; keep env fallbacks during transition.
- **Rollback:** Revert per service.
- **Priority:** P1
- **Status:** PENDING

---

## R0-010: Standardize CORS variable naming

- **ID:** R0-010
- **Domain:** Configuration
- **Problem:** `ai-gateway` reads `CORS_ORIGIN` from env, but docs and `.env.example` use `AI_GATEWAY_CORS_ORIGIN`.
- **Evidence:** `services/ai-gateway/security-config.mjs:20`, `.env.example:128`
- **Target:** Standardize on `AI_GATEWAY_CORS_ORIGIN` everywhere.
- **Risk:** Low
- **Dependencies:** None
- **Files:** `services/ai-gateway/security-config.mjs`, `.env.example`
- **Tests:** `services/ai-gateway/test/security-config.test.mjs`
- **Migration:** Update env reader.
- **Rollback:** Revert env reader.
- **Priority:** P2
- **Status:** PENDING

---

## R0-011: Remove deprecated environment variables

- **ID:** R0-011
- **Domain:** Configuration
- **Problem:** `AI_GATEWAY_PROVIDER_TOKEN`, `UPSTREAM_API_KEY`, `PROVIDER_TOKEN` are documented in `.env.example` but not used in current code.
- **Evidence:** `.env.example`, grep for usage
- **Target:** Remove from `.env.example` and any references in docs.
- **Risk:** Low
- **Dependencies:** None
- **Files:** `.env.example`, `docs/**`
- **Tests:** None
- **Migration:** Remove variables.
- **Rollback:** Restore variables.
- **Priority:** P4
- **Status:** PENDING

---

## R0-012: Add startup config validation

- **ID:** R0-012
- **Domain:** Reliability
- **Problem:** Services start without required secrets and fail at first request.
- **Evidence:** All Node services lack startup-time config validation.
- **Target:** Add startup validation in each service (or via `packages/config`) that fails fast on missing required config.
- **Risk:** Low
- **Dependencies:** R0-009
- **Files:** All services
- **Tests:** Add startup-failure tests.
- **Migration:** Add validation at top of `create*Server` functions.
- **Rollback:** Remove validation.
- **Priority:** P1
- **Status:** PENDING

---

## R0-013: Establish automation source-of-truth

- **ID:** R0-013
- **Domain:** DevEx
- **Problem:** `.agents/skills/z-platform/SKILL.md` and `.claude/skills/z-platform/SKILL.md` are identical but maintained separately.
- **Evidence:** Byte-identical 102-line files.
- **Target:** Create `automation/skills/z-platform/SKILL.md` as canonical. Generate `.agents/` and `.claude/skills/` from it. Document in `automation/README.md`.
- **Risk:** Low
- **Dependencies:** None
- **Files:** `automation/`, `.agents/`, `.claude/`
- **Tests:** Add generation script test.
- **Migration:** Move canonical, generate compatibility layers.
- **Rollback:** Restore original files.
- **Priority:** P3
- **Status:** PENDING

---

## R0-014: Add architecture CI tests

- **ID:** R0-014
- **Domain:** CI
- **Problem:** No CI enforcement of dependency direction, forbidden imports, or contract duplication.
- **Evidence:** `.github/workflows/` lacks architecture test job.
- **Target:** Add `architecture.yml` workflow with import scanning, forbidden dependency checks, and contract validation.
- **Risk:** Low
- **Dependencies:** R1-001 through R1-004
- **Files:** `.github/workflows/architecture.yml`
- **Tests:** N/A (CI workflow)
- **Migration:** Add workflow.
- **Rollback:** Remove workflow.
- **Priority:** P1
- **Status:** PENDING

---

## R0-015: Document data retention and deletion policies

- **ID:** R0-015
- **Domain:** Security
- **Problem:** No documented retention or deletion semantics for any data store.
- **Evidence:** `docs/architecture/data-ownership.md` gaps section.
- **Target:** Add retention and deletion policies to `data-ownership.md` and implement TTL/cleanup where missing.
- **Risk:** Low
- **Dependencies:** None
- **Files:** `docs/architecture/data-ownership.md`, service code
- **Tests:** None
- **Migration:** Document first, implement later.
- **Rollback:** N/A (documentation only)
- **Priority:** P2
- **Status:** PENDING

---

## R0-016: Add encryption-at-rest for Redis stores

- **ID:** R0-016
- **Domain:** Security
- **Problem:** Redis data (provider keys, alerts, sessions, webhooks) is stored unencrypted on Docker volumes.
- **Evidence:** `compose.yml` Redis service has no encryption config.
- **Target:** Enable Redis AOF/RDB encryption or migrate sensitive data to encrypted stores.
- **Risk:** Medium
- **Dependencies:** None
- **Files:** `compose.yml`, service code
- **Tests:** None
- **Migration:** Enable Redis encryption in Compose; verify compatibility.
- **Rollback:** Disable encryption.
- **Priority:** P2
- **Status:** PENDING

---

## R0-017: Add contract compatibility tests

- **ID:** R0-017
- **Domain:** Contracts
- **Problem:** `packages/contracts/schemas/` has schemas but no automated compatibility testing.
- **Evidence:** `packages/contracts/test/agent-contracts.test.mjs`, `packages/contracts/test/zarvis-schema.test.mjs`
- **Target:** Add CI gate that validates all schemas are valid JSON Schema Draft 7 and that producers/consumers match documented versions.
- **Risk:** Low
- **Dependencies:** None
- **Files:** `packages/contracts/test/`, `.github/workflows/`
- **Tests:** CI gate
- **Migration:** Add test script.
- **Rollback:** Remove test.
- **Priority:** P1
- **Status:** PENDING

---

## R0-018: Document AI Gateway as sole upstream boundary

- **ID:** R0-018
- **Domain:** Security
- **Problem:** `phase6-api` and `zc` also call upstream AI providers directly, bypassing the AI Gateway in some paths.
- **Evidence:** `services/phase6-api/app.py` calls upstream providers directly. `services/zc` may also call providers.
- **Target:** Audit all upstream AI calls. Route all browser/client AI requests through `ai-gateway`. Document exceptions and approval requirements.
- **Risk:** Medium
- **Dependencies:** None
- **Files:** `services/phase6-api/app.py`, `services/zc/`, docs
- **Tests:** Verify no browser-accessible path calls upstream providers directly.
- **Migration:** Redirect external AI calls through ai-gateway.
- **Rollback:** Revert redirects.
- **Priority:** P0
- **Status:** PENDING

---

## R0-019: Document production approval requirements

- **ID:** R0-019
- **Domain:** Operations
- **Problem:** Production approval requirements are mentioned in docs but not enforced in code/CI.
- **Evidence:** `docs/operations/production-master.md`
- **Target:** Add `PENDING_OPERATOR` checks in CI for production deployment workflows. Ensure `deploy-production.yml` requires manual approval gate.
- **Risk:** Low
- **Dependencies:** None
- **Files:** `.github/workflows/deploy-production.yml`, docs
- **Tests:** N/A
- **Migration:** Add `environment:` with `url` and required reviewers.
- **Rollback:** Remove environment protection.
- **Priority:** P1
- **Status:** PENDING

---

## R0-020: Remove stale submodule reference

- **ID:** R0-020
- **Domain:** Cleanup
- **Problem:** `.gitmodules` references `apps/zdash` submodule which is not present in the repo.
- **Evidence:** `.gitmodules`
- **Target:** Remove `.gitmodules` entry or add the submodule if still needed.
- **Risk:** Low
- **Dependencies:** None
- **Files:** `.gitmodules`
- **Tests:** None
- **Migration:** Remove entry.
- **Rollback:** Restore entry.
- **Priority:** P4
- **Status:** PENDING

---

## R0-021: Migrate zc implementation into z-platform

- **ID:** R0-021
- **Domain:** Architecture
- **Problem:** `services/zc` in z-platform is a minimal shell. The full implementation lives in `/home/cvsz/zc`.
- **Evidence:** z-platform `services/zc` has 152 files; `/home/cvsz/zc` has 350 files.
- **Target:** Merge implementation files from `/home/cvsz/zc/app`, `/home/cvsz/zc/config`, `/home/cvsz/zc/tests`, etc. into `services/zc`.
- **Risk:** Medium
- **Dependencies:** R0-002 (fix cross-service import)
- **Files:** `services/zc/app/**`, `services/zc/config/**`, `services/zc/tests/**`
- **Tests:** Run zc test suite.
- **Migration:** Copy missing files; preserve existing z-platform structure.
- **Rollback:** Revert added files.
- **Priority:** P1
- **Status:** COMPLETED

---

## R0-022: Migrate z-prov into z-platform

- **ID:** R0-022
- **Domain:** Architecture
- **Problem:** `z-prov` is a standalone provider management service that belongs in the platform.
- **Evidence:** `/home/cvsz/z-prov` contains provider adapters, control adapters, sandbox egress, enterprise vault.
- **Target:** Copy `z-prov` into `services/z-prov` in z-platform.
- **Risk:** Medium
- **Dependencies:** None
- **Files:** `services/z-prov/**`
- **Tests:** Run z-prov test suite.
- **Migration:** Copy all non-secret files.
- **Rollback:** Revert added files.
- **Priority:** P1
- **Status:** COMPLETED

---

## R0-023: Consolidate zcoder into zc

- **ID:** R0-023
- **Domain:** Architecture
- **Problem:** `/home/cvsz/zcoder` and `/home/cvsz/zc` are the same product (zcoder) maintained as separate repos.
- **Evidence:** Both have identical top-level structure, same README, same product name.
- **Target:** Use `/home/cvsz/zc` as canonical. Deprecate `/home/cvsz/zcoder`.
- **Risk:** Low
- **Dependencies:** R0-021
- **Files:** N/A (documentation only)
- **Tests:** N/A
- **Migration:** Document zc as canonical zcoder implementation.
- **Rollback:** N/A
- **Priority:** P2
- **Status:** COMPLETED

---

## R0-024: Migrate zai-coder core backend

- **ID:** R0-024
- **Domain:** Architecture
- **Problem:** `apps/zaicoder` in z-platform is a minimal shell. The full zai-coder backend is in `/home/cvsz/zai-coder`.
- **Evidence:** z-platform `apps/zaicoder` has 29 files; `/home/cvsz/zai-coder` has 6924 files.
- **Target:** Migrate core backend modules (CLI, gateway client, MCP connector, streaming, model preflight) into `apps/zaicoder/backend`. Do NOT bulk-copy entire repo.
- **Risk:** Medium
- **Dependencies:** R0-021
- **Files:** `apps/zaicoder/backend/src/zaicoder/**`
- **Tests:** Run zaicoder backend tests.
- **Migration:** Copy core modules; preserve clean shell structure.
- **Rollback:** Revert added files.
- **Priority:** P2
- **Status:** PENDING
