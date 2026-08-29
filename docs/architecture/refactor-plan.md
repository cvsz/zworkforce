# Refactor Plan

## Phase R0 — Repository Inventory (current phase)

**Status:** In progress

**Deliverables:**
- `docs/architecture/repository-map.md` — Complete inventory of apps, services, packages, tools, scripts, deploy, docs, tests, .github
- `docs/architecture/feature-ownership.md` — Machine-readable ownership catalog
- `docs/architecture/duplication-audit.md` — Duplication report with classifications
- `docs/architecture/dependency-rules.md` — Allowed and prohibited dependency directions
- `docs/architecture/configuration.md` — Environment variable inventory with types, defaults, and gaps
- `docs/architecture/data-ownership.md` — Persistent store inventory
- `docs/architecture/event-catalog.md` — Async communication inventory
- `docs/architecture/refactor-plan.md` — This document
- `docs/architecture/refactor-checklist.md` — Machine-actionable backlog
- `docs/adr/ADR-001` through `ADR-008` — Architecture Decision Records
- `automation/README.md` — Automation source-of-truth guide

**No behavior changes in R0.**

---

## Phase R1 — Architecture Guardrails

**Objective:** Add CI-enforced rules that prevent architectural regression.

**Tasks:**
1. Add `packages/errors` with `HttpError` base class and status mapping.
2. Add `packages/http-server` with shared `createServer`, `readJson`, `sendJson`, `authBearer` primitives.
3. Add `packages/zarvis-auth` with shared `requireSecret`, `secretsMatch`, `assertOwnerEdge`, `ZARVIS_OWNER_GITHUB_ID`.
4. Add architecture tests that scan imports for forbidden patterns.
5. Add contract validation CI gate (JSON Schema validation for `packages/contracts/schemas/*.schema.json`).
6. Add configuration validation CI gate (schema validation for `.env.example` variables).

**Bounded PR:** One PR per shared package + architecture tests.

**Risk:** Low. Shared packages are additive; no existing code is modified until R2.

---

## Phase R2 — Shared Foundation

**Objective:** Consolidate duplicated infrastructure code into shared packages.

**Tasks:**
1. Migrate `services/agent-orchestrator/server.mjs` to use `packages/http-server` and `packages/errors`.
2. Migrate `services/billing-ledger/server.mjs` to use `packages/http-server` and `packages/errors`.
3. Migrate `services/workspace-runtime/server.mjs` to use `packages/http-server` and `packages/errors`.
4. Migrate `services/agent-provider/server.mjs` to use `packages/http-server` and `packages/errors`.
5. Migrate `apps/zwallet/server.mjs` to use `packages/http-server` and `packages/errors`.
6. Migrate `apps/zow/server.mjs` to use `packages/http-server` and `packages/errors`.
7. Migrate `apps/zchat/server.mjs` to use `packages/http-server` and `packages/errors`.
8. Migrate `apps/zvoice/server.mjs` to use `packages/http-server`, `packages/errors`, and `packages/zarvis-auth`.
9. Migrate zarvis-* services to use `packages/http-server`, `packages/errors`, and `packages/zarvis-auth`.
10. Fix `ai-gateway/index.js` auth to use `timingSafeEqual` (security defect).

**Bounded PR:** One PR per service/app migration. Each PR includes tests.

**Risk:** Medium. Requires careful import path management and regression testing.

---

## Phase R3 — Service Internals

**Objective:** Normalize each service independently.

**Tasks:**
1. **ai-gateway:** Extract provider adapters, retry logic, and key rotation into `services/ai-gateway/src/adapters/` and `services/ai-gateway/src/domain/`. Add typed request/response schemas.
2. **agent-orchestrator:** Split control plane (API, approval, scheduling) from execution plane (worker dispatch, sandbox requests). Introduce `services/agent-orchestrator/src/api/`, `services/agent-orchestrator/src/application/`, `services/agent-orchestrator/src/domain/`.
3. **agent-provider:** Introduce `services/agent-provider/src/api/`, `services/agent-provider/src/application/`, `services/agent-provider/src/domain/`. Add proper database abstraction (replace file JSON with a queue port).
4. **billing-ledger:** Introduce layered structure. Add persistent store abstraction.
5. **workspace-runtime:** Introduce layered structure. Add approval policy engine.
6. **zarvis-orchestrator:** Introduce layered structure. Extract session store to adapter.
7. **zarvis-task-gateway:** Remove direct import of `AgentOrchestratorError` from agent-orchestrator. Use shared error package.

**Bounded PR:** One service per PR.

**Risk:** Medium. Internal refactoring with full regression coverage required.

---

## Phase R4 — Application Boundaries

**Objective:** Thin applications and extract reusable backend/platform logic.

**Tasks:**
1. **zchat:** Extract gateway proxy client to shared SDK or typed client.
2. **zvoice:** Extract local conversation fallback to `packages/voice`.
3. **zwallet:** Already thin; verify no additional logic is added.
4. **zow:** Already thin; verify no additional logic is added.
5. **zaicoder:** Extract workspace metadata adapter and gateway client to shared packages.
6. **zarvis-console:** Extract owner access and upstream proxy to shared packages.

**Bounded PR:** One app per PR.

**Risk:** Low. Apps are already thin.

---

## Phase R5 — Automation Consolidation

**Objective:** Normalize agent/prompt/skill sources.

**Tasks:**
1. Create `automation/agents/`, `automation/prompts/`, `automation/skills/`, `automation/policies/`, `automation/workflows/`.
2. Move `agents/*.md` to `automation/agents/`.
3. Move `.codex/prompts/*` to `automation/prompts/`.
4. Establish `automation/skills/z-platform/SKILL.md` as canonical.
5. Generate `.agents/skills/z-platform/SKILL.md` and `.claude/skills/z-platform/SKILL.md` from canonical source.
6. Create `automation/README.md` documenting source-of-truth behavior.

**Bounded PR:** One automation surface per PR.

**Risk:** Low. No runtime code changes.

---

## Phase R6 — Deployment

**Objective:** Normalize Docker, Compose, environment and deployment assets.

**Tasks:**
1. Consolidate Node Dockerfiles into `deploy/docker/node-service.Dockerfile` (multi-stage, healthcheck, `.dockerignore`).
2. Replace `ai-gateway.Dockerfile` with generic node-service build.
3. Add `services/voice-agent/Dockerfile` and `services/voice-gateway/Dockerfile` if missing.
4. Consolidate Compose files into `compose.yaml` (base), `compose.dev.yaml`, `compose.test.yaml`, `compose.staging.yaml` using profiles.
5. Remove `docker-compose.phase6.yml` in favor of profile-based composition.
6. Create `deploy/compose/`, `deploy/kubernetes/`, `deploy/helm/`, `deploy/terraform/`, `deploy/environments/`, `deploy/scripts/`.
7. Add `.dockerignore` to all services that lack it.

**Bounded PR:** One deployment asset category per PR.

**Risk:** Medium. Operator coordination required to verify local and staging workflows.

---

## Phase R7 — CI/CD

**Objective:** Consolidate workflows and add architecture enforcement.

**Tasks:**
1. Extract common Node/Python setup into reusable composite actions.
2. Add architecture test workflow (import scan, forbidden dependency check).
3. Add contract validation workflow.
4. Add configuration validation workflow.
5. Consolidate duplicate smoke test logic.

**Bounded PR:** One CI refactor per PR.

**Risk:** Low. CI-only changes.

---

## Phase R8 — Cleanup

**Objective:** Remove verified dead code and stale compatibility layers.

**Tasks:**
1. Remove deprecated env vars (`AI_GATEWAY_PROVIDER_TOKEN`, `UPSTREAM_API_KEY`, `PROVIDER_TOKEN`).
2. Remove `apps/zdash` submodule reference (not present in repo).
3. Remove `zarvis-live-evidence/` and `zarvis-owner-domain-bundle/` if not version-controlled.
4. Remove `.env.zarvis.voice.local.bak`.
5. Remove `FETCH_HEAD`.
6. Audit and remove stale prompts in `agents/` if superseded by canonical `automation/` sources.

**Bounded PR:** One cleanup category per PR.

**Risk:** Low. Dead code removal with evidence.

---

## Phase R9 — Production Verification

**Objective:** Run all gates and update evidence.

**Tasks:**
1. Run full CI suite on clean main.
2. Run `make bootstrap && make dev` smoke test.
3. Verify architecture tests pass.
4. Verify contract validation passes.
5. Verify secret scanning passes.
6. Verify SBOM and provenance generation.
7. Update `docs/operations/production-master.md` with current evidence.
8. Mark all features as `PRODUCTION_APPROVED` only after operator sign-off.

**Risk:** Low. Verification only.
