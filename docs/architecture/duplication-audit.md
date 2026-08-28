# Duplication Audit

## Classification key

- `KEEP_LOCAL` — Stable, small, and unlikely to be reused; keep in place.
- `SHARE_PACKAGE` — Extract to `packages/` for reuse across apps and services.
- `MOVE_TO_SERVICE` — Move into the owning service and expose via API.
- `DELETE` — Remove dead or superseded code.
- `LEGACY_ADAPTER` — Retain as a thin compatibility shim during migration.

## 1. HTTP server primitives

**Evidence:** `send()`/`json()`/`writeJson()` is implemented in 12+ files. `readJson()`/`readJsonBody()`/`body()` is implemented in 14+ files. `authorized()` with `timingSafeEqual` is implemented in 7+ files. Custom `Error` subclasses with `status` are implemented in 15+ files.

**Files:**

| File | send | readJson | authorized | Error class |
|---|---|---|---|---|
| `services/agent-orchestrator/server.mjs` | json() | body() | authorized() | AgentOrchestratorError |
| `services/agent-provider/server.mjs` | send() | readJson() | authorized() | — |
| `services/billing-ledger/server.mjs` | send() | readJson() | authorized() | BillingLedgerError |
| `services/workspace-runtime/server.mjs` | send() | readJson() | authorized() | WorkspaceRuntimeError |
| `services/voice-gateway/index.mjs` | sendJson() | readJson() | parseBearer() | — |
| `services/zarvis-orchestrator/src/server.mjs` | writeJson() | readJsonBody() | assertOwnerServiceRequest() | OwnerAccessError, ConfirmationRequiredError |
| `services/zarvis-task-gateway/server.mjs` | writeJson() | readJson() | assertOwner/assertWorker | TaskAccessError |
| `services/zarvis-memory/server.mjs` | writeJson() | readJson() | assertOwner/assertWorker | MemoryAccessError |
| `services/zarvis-action-gateway/server.mjs` | json() | readJson() | requireOwner/requireWorker | ActionError |
| `services/zarvis-proactive/server.mjs` | json() | readJson() | requireOwner/requireWorker | ProactiveError |
| `services/zarvis-perception/server.mjs` | writeJson() | readJson() | assertOwner/assertWorker | PerceptionAccessError |
| `apps/zchat/server.mjs` | send() | json() | — | — |
| `apps/zvoice/server.mjs` | send() | json() | secretsMatch | HttpError |
| `apps/zwallet/server.mjs` | send() | readJson() | — | — |
| `apps/zow/server.mjs` | send() | readJson() | — | — |
| `apps/zaicoder/web/server/http.mjs` | — | readJson() | — | — |
| `apps/zarvis-console/server.mjs` | writeJson() | readBody() | isOwnerRequest | — |

**Classification:** `SHARE_PACKAGE`

**Rationale:** These are stable, semantically identical capabilities (JSON body parsing with size limits, secure bearer auth, JSON response serialization, typed error classes). Centralizing them eliminates 100+ lines of duplication per service and ensures consistent behavior (e.g., body size limits, content-type checks, error shapes).

**Target:** `packages/http-server` (or similar) providing `createServer`, `readJson`, `sendJson`, `authBearer`, `HttpError`.

**Risk:** Low. Each service imports the shared primitives but keeps its own route handlers and domain logic.

## 2. ZARVIS owner access pattern

**Evidence:** `requireSecret()`, `secretsMatch()`, `assertOwner()`, `ZARVIS_OWNER_GITHUB_ID` are duplicated across:
- `services/zarvis-orchestrator/src/server.mjs`
- `services/zarvis-task-gateway/server.mjs`
- `services/zarvis-memory/server.mjs`
- `services/zarvis-action-gateway/server.mjs`
- `services/zarvis-proactive/server.mjs`
- `services/zarvis-perception/server.mjs`
- `apps/zarvis-console/server.mjs`
- `apps/zvoice/server.mjs`

**Classification:** `SHARE_PACKAGE`

**Target:** `packages/zarvis-auth` providing `requireSecret`, `secretsMatch`, `assertOwnerEdge`, `ZARVIS_OWNER_GITHUB_ID`.

**Risk:** Low. The pattern is well-defined and already consistent.

## 3. AI Gateway retry / fallback logic

**Evidence:** `services/ai-gateway/index.js` contains two large retry loops (one for OpenAI-compatible, one for Anthropic) with near-identical structure: key selection, 429 rotation, 401/403 invalidation, streaming pipe, abort handling.

**Classification:** `SHARE_PACKAGE` (within ai-gateway)

**Target:** Extract `ProviderClient` adapter with shared retry/fallback/rotation logic.

**Risk:** Low. Internal to ai-gateway.

## 4. Dockerfiles

**Evidence:**

| Dockerfile | Base | Multi-stage | Non-root | Pinned | Healthcheck |
|---|---|---|---|---|---|
| `deploy/docker/ai-gateway.Dockerfile` | node:20-alpine | No | Yes | Major only | No |
| `deploy/docker/node-service.Dockerfile` | node:20-alpine | No | Yes | Major only | No |
| `deploy/docker/next-service.Dockerfile` | node:20-alpine | No | Yes | Major only | No |
| `services/zc/Dockerfile` | python:3.12-slim-bookworm | No | Yes | Yes | Yes |
| `services/voice-agent/Dockerfile` | (exists) | — | — | — | — |
| `services/voice-gateway/Dockerfile` | (exists) | — | — | — | — |

**Classification:** `SHARE_PACKAGE` / `CONSOLIDATE`

**Target:** Consolidate Node service Dockerfiles into a single parameterized `deploy/docker/node-service.Dockerfile` (already exists for most services). Add multi-stage, `.dockerignore`, healthcheck, and deterministic installs. The `ai-gateway.Dockerfile` should be replaced by the generic one with a build ARG.

## 5. Compose files

**Evidence:** 6 compose files with significant overlap:
- `compose.yml` — main stack
- `compose.voice.yml` — voice overlay
- `compose.zarvis-local.yml` — zarvis local overlay
- `compose.zarvis-owner-domain.yml` — owner domain
- `compose.zarvis-owner-voice.yml` — owner voice
- `docker-compose.phase6.yml` — phase 6 external

Many services are defined identically across stacks (node-service base, healthchecks, networks, secrets).

**Classification:** `SHARE_PACKAGE`

**Target:** Consolidate into `compose.yaml` (base), `compose.dev.yaml`, `compose.test.yaml`, `compose.staging.yaml` using profiles and extends. Remove `docker-compose.phase6.yml` in favor of profile-based composition.

**Risk:** Medium. Requires operator coordination to verify local workflows.

## 6. Environment variables

**Evidence:** 223 lines in `.env.example` with ~80 variables. Duplicates include:
- `Z_PLATFORM_SERVICE_TOKEN` referenced in every service and app
- `AI_GATEWAY_CORS_ORIGIN` vs `CORS_ORIGIN` in ai-gateway
- `AGENT_PROVIDER_TIMEOUT_MS` vs `AGENT_SANDBOX_TIMEOUT_MS`
- `Z_PLATFORM_RELEASE_SHA` used in health endpoints
- Multiple provider key variables with similar patterns

**Classification:** `SHARE_PACKAGE`

**Target:** `packages/config` with typed schemas per domain (platform, ai, agent, workspace, billing, voice, zarvis).

## 7. Agent / prompt / skill duplication

**Evidence:**
- `.agents/skills/z-platform/SKILL.md` and `.claude/skills/z-platform/SKILL.md` are byte-identical (102 lines each).
- `.codex/AGENTS.md` references `.agents/skills/` and `.claude/skills/` as canonical.
- `agents/` contains 60+ agent persona definitions.
- `.codex/prompts/z-platform-scan-fix/` contains 7 phase prompts.

**Classification:** `LEGACY_ADAPTER` for `.claude/skills/` and `.agents/skills/` (generated from source). `KEEP_LOCAL` for `agents/` and `.codex/prompts/` until canonical source is established.

**Target:** Establish `automation/agents/`, `automation/prompts/`, `automation/skills/` as canonical. Generate `.agents/` and `.claude/skills/` from canonical source. Keep `.codex/` as compatibility layer.

## 8. Provider key validation scripts

**Evidence:**
- `scripts/verify-ai-multi-provider.sh`
- `scripts/verify-ai-streaming-upload.mjs`
- `scripts/verify-ai-upload.sh`
- `scripts/verify-ai-failover.sh`
- `scripts/verify-browser-credential-isolation.mjs`
- `scripts/verify-external-restore.sh`
- `scripts/verify-observability-stack.mjs`
- `scripts/verify-human-qa-and-identity.mjs`

Many share credential scanning, HTTP probing, and JSON assertion patterns.

**Classification:** `SHARE_PACKAGE`

**Target:** `tools/ops/` validation helpers reused by scripts.

## 9. Health endpoint shapes

**Evidence:** Health endpoints use inconsistent shapes:
- `services/ai-gateway`: `{ status: "ok", service: "ai-gateway", release_sha: "..." }`
- `services/agent-orchestrator`: `{ status: "ok", service: "agent-orchestrator", storage: "...", execution_enabled: true, external_traffic_enabled: false }`
- `services/billing-ledger`: `{ status: "ok", service: "billing-ledger", wallet_authority: false, card_data: false }`
- `services/workspace-runtime`: `{ status: "ok", service: "workspace-runtime", sandbox: "approval-gated" }`
- `apps/zchat`: `/health` includes backends, `/health/live` is minimal
- `apps/zvoice`: `/health` includes many fields, `/health/live` is minimal
- `services/zarvis-*`: `/healthz` with version and service-specific fields

**Classification:** `SHARE_PACKAGE`

**Target:** Standardize health response schema in `packages/contracts` with `HealthResponse` shape, and `packages/http-server` for `/health` and `/health/live` routing.

## 10. Error response shapes

**Evidence:** Error responses are inconsistent:
- ai-gateway: `{ error: { code: "...", message: "..." } }`
- agent-orchestrator: `{ error: "..." }` or `{ error: { message: "..." } }` (inconsistent)
- billing-ledger: `{ error: "..." }`
- workspace-runtime: `{ error: "..." }`
- zvoice: `{ error: { code: "...", message: "..." } }`
- zarvis-*: `{ error: { code: "...", message: "...", request_id: "..." } }`

**Classification:** `SHARE_PACKAGE`

**Target:** Standardize on `{ error: { code, message, request_id? } }` via shared response helper.

## 11. Security headers

**Evidence:**
- `ai-gateway` uses `helmet()` and `cors()`.
- `zvoice` defines a comprehensive `SECURITY_HEADERS` object.
- `zarvis-*` services define partial security headers inline.
- Most other services have no security headers.

**Classification:** `SHARE_PACKAGE`

**Target:** Standardize security headers in `packages/http-server`.

## 12. Body size limits

**Evidence:** Body size limits vary wildly:
- `agent-orchestrator`: 100,000 chars
- `agent-provider`: 1,000,000 bytes
- `billing-ledger`: 100,000 chars
- `workspace-runtime`: 100,000 chars
- `zarvis-orchestrator`: 32,768 bytes
- `zarvis-task-gateway`: 64 KB
- `zarvis-memory`: 64 KB
- `zarvis-action-gateway`: 64 KB
- `zarvis-proactive`: 64 KB
- `zarvis-perception`: 8 MB
- `zvoice`: 32 KB
- `zchat`: 100,000 chars
- `zow`: 100,000 chars
- `zwallet`: no limit

**Classification:** `SHARE_PACKAGE`

**Target:** Centralize body size limits per endpoint category in shared config.

## 13. Service token auth inconsistency

**Evidence:**
- `ai-gateway/index.js` uses `token !== process.env.Z_PLATFORM_SERVICE_TOKEN` (NOT timing-safe).
- All other services use `timingSafeEqual`.
- This is a **security defect** per invariant #50.

**Classification:** `SHARE_PACKAGE` (fix required)

**Target:** Replace with shared `authBearer()` using `timingSafeEqual`.

## 14. Contract schema duplication

**Evidence:**
- `packages/contracts/schemas/` contains 26 JSON schemas.
- `services/zarvis-orchestrator/src/contracts.mjs` defines `ValidationError`, `UnsupportedIntentError`, `IdempotencyConflictError` as code, not reusable across services.
- `schemas/operations/` and `schemas/release/` are separate from `packages/contracts/schemas/`.

**Classification:** `SHARE_PACKAGE` / `MOVE_TO_SERVICE`

**Target:** Move all cross-boundary schemas to `packages/contracts/schemas/`. Move ops/release schemas to `schemas/` with clear ownership.

## 15. Test utilities

**Evidence:** Each service has its own test setup with duplicated `request()` helpers, env overrides, and assertions.

**Classification:** `SHARE_PACKAGE`

**Target:** `packages/testing` with `createTestServer`, `assertJsonResponse`, `mockEnv`.
