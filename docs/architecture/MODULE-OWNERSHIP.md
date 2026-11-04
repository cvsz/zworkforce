# ZWorkforce Module Ownership

**Generated:** 2026-11-05 UTC+7  
**Baseline SHA:** `1249243958280c5499a564180d32f6677d8791ff`  
**Authority:** [`module-registry.yaml`](./module-registry.yaml)

> [!IMPORTANT] ไฟล์นี้คือ canonical ownership map — ก่อนแก้ไขโมดูลใดให้ตรวจที่นี่ก่อนว่า canonical source อยู่ที่ใด

## Canonical Module Ownership Table

| Module | Canonical Path | Language | Type | Release Scope | Owner |
|---|---|---|---|---|---|
| **zworkforce** (control plane) | `zworkforce/` | Python | Control Plane | v3.0.4 required / complete | cvsz |
| **ztrader_intel** | `packages/ztrader/zeaz-intelligence/` | Python | Service Package | forward roadmap | cvsz |
| **zider** | `packages/zider/` | Python | Browser Companion | forward roadmap | cvsz |
| **zarvis** | `packages/zarvis/` ← CANONICAL | Mixed | Platform Package | forward roadmap | cvsz |
| **zeto** | `packages/zeto/` | JavaScript | Content Factory | forward roadmap | cvsz |
| **zsp-aitool** | `packages/zsp-aitool/` | TypeScript | Web App | forward roadmap | cvsz |
| **wall-street** | `packages/wall-street/` | JavaScript | Service Package | forward roadmap | cvsz |
| **contracts** | `packages/contracts/` | TypeScript | Shared Types | forward roadmap | cvsz |
| **ai-gateway** | `services/ai-gateway/` | JavaScript | Microservice | v3.0.4 required / complete | cvsz |
| **billing-ledger** | `services/billing-ledger/` | JavaScript | Microservice | v3.0.4 required / complete | cvsz |
| **workspace-runtime** | `services/workspace-runtime/` | JavaScript | Microservice | v3.0.4 required / complete | cvsz |
| **zarvis-services** (canonical) | `packages/zarvis/services/` ← CANONICAL | Mixed | Microservices | forward roadmap | cvsz |
| **zarvis-services** (mirror) | `services/zarvis-*/` | Mixed | Mirror | forward roadmap | cvsz |
| **zc** | `services/zc/` | Python | Microservice | forward roadmap | cvsz |
| **zarvis-console** (canonical) | `packages/zarvis/apps/zarvis-console/` ← CANONICAL | JavaScript | Web App | forward roadmap | cvsz |
| **zarvis-console** (mirror) | `apps/zarvis-console/` | JavaScript | Mirror | forward roadmap | cvsz |
| **zchat** | `apps/zchat/` | JavaScript | Web App | forward roadmap | cvsz |
| **zow** | `apps/zow/` | JavaScript | Web App | v3.0.4 required / complete | cvsz |
| **zwallet** | `apps/zwallet/` | JavaScript | Web App | forward roadmap | cvsz |
| **zaicoder** | `apps/zaicoder/` | Mixed | Web App | forward roadmap | cvsz |
| **ZWorkforceClient** | `ZWorkforceClient/` | C# | Windows Client | v3.0.4 required / complete | cvsz |
| **Kubernetes** | `infrastructure/kubernetes/` | YAML | Infrastructure | external evidence | cvsz |
| **Cloudflare Terraform** | `infrastructure/terraform/cloudflare/` | Terraform | Infrastructure | external evidence | cvsz |

## Critical Ownership Notes

### 1. Z.A.R.V.I.S. Canonical vs Mirror

> [!WARNING] `packages/zarvis/services/` is AHEAD of `services/` for two services:

| Service | Canonical (packages/zarvis/) | Mirror (services/) | Drift |
|---|---|---|---|
| `zarvis-action-gateway` | ✅ | ✅ (identical) | None |
| `zarvis-memory` | ✅ | ✅ (identical) | None |
| `zarvis-perception` | ✅ | ✅ (identical) | None |
| `zarvis-proactive` | ✅ | ✅ (identical) | None |
| `zarvis-owner-voice-edge` | ✅ | ✅ (identical) | None |
| **zarvis-orchestrator** | ✅ | ⚠️ BEHIND | packages/zarvis/ has `live_voice.mjs`, `skill-catalog.mjs`, extra tests |
| **zarvis-task-gateway** | ✅ | ⚠️ BEHIND | packages/zarvis/ has `durable-adapters.mjs`, `orchestrator-core.mjs`, README differs |
| **voice-agent** | ✅ | ⚠️ BEHIND | packages/zarvis/ has extended `healthcheck.py` with provider registry reporting |

**Rule:** When updating zarvis-orchestrator, zarvis-task-gateway, or voice-agent — always edit `packages/zarvis/services/` first, then sync to `services/` if that copy is still referenced by deployment.

### 2. Apps with Mirror Copies

| App | Canonical | Mirror |
|---|---|---|
| zarvis-console | `packages/zarvis/apps/zarvis-console/` | `apps/zarvis-console/` |
| zvoice | `packages/zarvis/apps/zvoice/` | `apps/zvoice/` |
| zarvis-windows | `packages/zarvis/apps/zarvis-windows/` | `apps/zarvis-windows/` |

Verify which copy is referenced in `compose.zarvis-*.yml` and `.github/workflows/zarvis.yml` before modifying either.

### 3. Dead Files for Removal

The following files are confirmed dead (no consumers, no CI references):

| File | Type | Evidence |
|---|---|---|
| `packages/zeto/test.txt` | Test runner stdout capture | Committed accidentally; no test references |
| `packages/zeto/test_out.txt` | Test runner stdout capture | Committed accidentally; no test references |
| `packages/zeto/test/operatorApi.integration.test.js.bak` | Backup of integration test | No `.bak` consumer; superseded |
| `packages/zeto/test/operatorRuntime.integration.test.js.bak` | Backup of integration test | No `.bak` consumer; superseded |

**Safe to remove** after PR review (not deleted here to maintain minimum-safe-diff principle).

### 4. Release-Scoped Modules (v3.0.4)

Modules required for v3.0.4 corrective candidate with active remediation:

| Module | Key Remediation (2026-11-05) |
|---|---|
| `zworkforce/` | Python compile clean; doctor gate; existing tests passing |
| `services/ai-gateway/` | Tenant-scoped Redis rate-limit key pools; `X-Tenant-ID` enforcement |
| `services/billing-ledger/` | Durable PostgreSQL store; migration `001_durable_billing_ledger.sql`; idempotency |
| `services/workspace-runtime/` | Four-eyes HMAC approval; expiry check; signature binding |
| `apps/zow/` | Operator token gate; four-eyes HMAC authorization |
| `packages/zider/` | CORS lockdown; tenant-scoped PDF; auth hardening |
| `deploy/cloudflare/tunnel-ingress.yml` | PostgreSQL route removed |
| `infrastructure/terraform/cloudflare/` | `zwsl_postgres_origin` variable + route removed |
| `infrastructure/kubernetes/` | `zc-api` → `zcoder-api` rename (wire service) |
| `compose.open-webui.yml` | fail-closed auth config; no admin auto-registration |
| `.gitmodules` / `.github/workflows/ci.yml` | HTTPS submodule checkout; SSH keys removed |
