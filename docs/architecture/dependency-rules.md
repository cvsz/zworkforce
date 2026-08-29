# Dependency Rules

## Target direction

```text
apps
  ↓
platform SDK / contracts
  ↓
services
  ↓
domain adapters
  ↓
external providers
```

## Allowed dependencies

| From | To | Allowed |
|---|---|---|
| `apps/*` | `packages/contracts` | Yes |
| `apps/*` | `packages/*` (platform SDK) | Yes |
| `apps/*` | `services/*` (via HTTP API only) | Yes |
| `services/*` | `packages/contracts` | Yes |
| `services/*` | `packages/*` (platform SDK) | Yes |
| `services/*` | external providers (via adapter) | Yes |
| `packages/*` | external providers | No |
| `packages/*` | services/* | No |
| `services/*` | apps/* | No |
| `apps/*` | apps/*` | No |

## Current violations (evidence)

### 1. Service-to-service implementation import

**Violation:** `services/zarvis-task-gateway/server.mjs` imports `AgentOrchestratorError` from `../agent-orchestrator/server.mjs`.

**File:** `services/zarvis-task-gateway/server.mjs:4`

**Risk:** Creates coupling between service internals. If agent-orchestrator changes its error class, zarvis-task-gateway breaks.

**Fix:** Move shared error base class to `packages/errors` or define local `TaskError` with compatible shape.

### 2. Domain logic depending on vendor SDK

**Evidence:** `services/ai-gateway/index.js` imports `ioredis` and `redis` directly in domain logic. Redis is used for provider key pools and rate limiting.

**Current:** `ai-gateway` is the AI Gateway boundary, so direct Redis usage is acceptable within that service. However, the retry/fallback logic is tightly coupled to Express middleware.

**Target:** Extract provider adapter and retry logic into `services/ai-gateway/src/adapters/` with interfaces.

### 3. Browser code referencing server secrets

**Evidence:** CI `validate.yml` already blocks `VITE_*`, `NEXT_PUBLIC_*`, `PUBLIC_*` env vars containing `Z_PLATFORM_SERVICE_TOKEN`, `AI_GATEWAY_PROVIDER_TOKEN`, `UPSTREAM_API_KEY`, `PROVIDER_TOKEN`. No violations found in current code.

**Status:** Enforced in CI.

### 4. App-to-app imports

**Evidence:** No direct app-to-app imports found.

**Status:** Clean.

## Proposed enforcement

Add architecture CI checks that:
1. Scan `import`/`require` statements for forbidden patterns.
2. Fail when `apps/*` imports `services/*/src/**` directly.
3. Fail when `packages/*` imports `services/*` or `apps/*`.
4. Fail when browser bundles contain server-only credential identifiers.
5. Fail when `domain/` folders (if introduced) import vendor SDKs.
