# ZWorkforce Final Directory Structure

**Generated:** 2026-11-05 UTC+7  
**Baseline SHA:** `1249243958280c5499a564180d32f6677d8791ff`  
**Total Tracked Files:** 3,092

> [!NOTE] โครงสร้างนี้สะท้อนสถานะจริงของ repository หลังการ remediation ครั้งนี้ ไม่ใช่โครงสร้างเป้าหมายในอนาคต

## Tree (เฉพาะ directory หลัก)

```
zworkforce/                           # Root monorepo
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                    # Main CI (modified: SSH keys removed, HTTPS submodules)
│   │   ├── zarvis.yml                # Z.A.R.V.I.S. workspace CI
│   │   ├── windows-client.yml        # Windows client build/sign
│   │   ├── dependency-review.yml     # Dependency security review
│   │   ├── billing-ledger-postgres.yml # (NEW) Billing ledger PostgreSQL CI
│   │   └── request-independent-review.yml
│   ├── rulesets/main.json            # Branch protection ruleset
│   └── CODEOWNERS
│
├── zworkforce/                       # 🔵 Core Python control plane
│   ├── api.py, app.py, main.py       # FastAPI application entry
│   ├── repository.py                 # Durable state (SQLite + PostgreSQL)
│   ├── scheduler.py                  # Leader-elected cron
│   ├── worker.py                     # Task queue consumer
│   ├── outbox.py                     # Transactional webhook outbox
│   ├── auth.py                       # Auth / RBAC
│   ├── mcp_server.py                 # MCP 2026-07-28 stateless endpoint
│   ├── tunnel.py                     # Reverse tunnel
│   └── cli.py                        # CLI (doctor command)
│
├── packages/
│   ├── zarvis/                       # 🟢 Z.A.R.V.I.S. CANONICAL platform
│   │   ├── services/                 # Microservices (canonical source)
│   │   │   ├── zarvis-orchestrator/  # +live_voice.mjs, +skill-catalog.mjs
│   │   │   ├── zarvis-task-gateway/  # +durable-adapters.mjs, +orchestrator-core.mjs
│   │   │   ├── voice-agent/          # +extended healthcheck with provider registry
│   │   │   ├── voice-gateway/
│   │   │   ├── zarvis-action-gateway/
│   │   │   ├── zarvis-memory/
│   │   │   ├── zarvis-perception/
│   │   │   ├── zarvis-proactive/
│   │   │   └── zarvis-owner-voice-edge/
│   │   ├── apps/
│   │   │   ├── zarvis-console/
│   │   │   ├── zarvis-windows/
│   │   │   └── zvoice/
│   │   ├── packages/
│   │   │   ├── contracts/            # TypeScript inter-service types
│   │   │   └── voice-client/
│   │   └── tools/zctl/               # Z.A.R.V.I.S. CLI tool
│   ├── zider/                        # Browser companion (FastAPI BFF)
│   │   └── server/
│   │       ├── app/
│   │       │   ├── config.py         # (modified: auth + CORS config)
│   │       │   ├── main.py           # (modified: CORS lockdown)
│   │       │   ├── routes/api.py     # (modified: tenant scope enforcement)
│   │       │   └── services/pdf_service.py  # (modified: tenant-scoped store)
│   │       └── tests/
│   │           └── test_zider_api.py # (modified: conditional fastapi import)
│   ├── ztrader/zeaz-intelligence/    # Trading intelligence sidecar
│   │   └── src/ztrader_intel/
│   │       ├── store.py              # (modified: tenant-scoped AnalysisStore)
│   │       ├── events.py             # (modified: per-tenant EventBus)
│   │       └── api.py                # (modified: IntelTenantScope dependency)
│   ├── zeto/                         # Content factory
│   │   └── test/
│   │       ├── operatorApi.integration.test.js.bak    # dead — queue for removal
│   │       └── operatorRuntime.integration.test.js.bak  # dead — queue for removal
│   ├── zsp-aitool/                   # Next.js studio app
│   ├── wall-street/
│   ├── contracts/
│   ├── zksato/                       # [git submodule — HTTPS]
│   ├── zmovie/                       # [git submodule — HTTPS]
│   ├── zok/                          # [git submodule — HTTPS]
│   └── zttshop-php/                  # [git submodule — HTTPS]
│
├── services/
│   ├── ai-gateway/                   # (modified: tenant rate-limit isolation)
│   ├── billing-ledger/               # (modified: PostgreSQL durable store)
│   │   ├── server.mjs                # (modified: fail-closed PG, SQLite fallback)
│   │   ├── postgres-store.mjs        # (NEW)
│   │   ├── migrations/
│   │   │   └── 001_durable_billing_ledger.sql  # (NEW)
│   │   └── test/
│   │       ├── postgres-store.test.mjs  # (NEW)
│   │       └── runtime-safety.test.mjs  # (NEW)
│   ├── workspace-runtime/            # (modified: four-eyes HMAC gate)
│   ├── zarvis-*/                     # ⚠️ MIRROR of packages/zarvis/services/
│   ├── zc/                           # ZCoder Python service
│   └── zc-api/                       # ZCoder Node.js API (port 8420/8421 → zcoder-api)
│
├── apps/
│   ├── zow/                          # (modified: operator token + four-eyes gate)
│   ├── zchat/
│   ├── zwallet/
│   ├── zarvis-console/               # ⚠️ MIRROR of packages/zarvis/apps/zarvis-console/
│   ├── zaicoder/
│   ├── agent-control-panel/
│   └── frontend/
│
├── ZWorkforceClient/                 # Windows native WinUI 3 (C#/.NET)
│
├── infrastructure/
│   ├── kubernetes/
│   │   ├── base/
│   │   │   ├── deployments.yaml      # (modified: zcoder-api renamed from zc-api)
│   │   │   ├── services.yaml         # (modified: zcoder-api renamed)
│   │   │   └── poddisruptionbudgets.yaml  # (modified: zcoder-api renamed)
│   │   └── overlays/production/kustomization.yaml  # (modified: zcoder-api refs)
│   └── terraform/cloudflare/
│       └── zworkforce.tf             # (modified: PostgreSQL route removed)
│
├── deploy/
│   ├── caddy/Caddyfile               # Open WebUI bound to 127.0.0.1
│   ├── cloudflare/tunnel-ingress.yml  # (modified: PostgreSQL ingress removed)
│   └── docker/
│
├── tests/                            # Repository-level policy tests
│   ├── test_repository_policy.py     # (modified: +k8s unique IDs test)
│   ├── test_cloudflare_ingress.py    # (modified: +PostgreSQL ingress test)
│   ├── test_submodule_security.py    # (NEW)
│   └── test_terraform_plan_approval.py  # (NEW)
│
├── docs/
│   ├── MASTER-PROMPT-031126.md       # (untracked — preserved per AGENTS.md)
│   ├── PRODUCTION-EVIDENCE.md        # Production evidence ledger (Stages A–I)
│   ├── security/
│   │   ├── OPEN-WEBUI-CUSTOMER-BOUNDARY.md  # (NEW)
│   │   └── PUBLIC-SUBMODULE-CHECKOUT.md     # (NEW)
│   ├── architecture/                 # (NEW directory with 7 docs)
│   │   ├── FILE-INVENTORY.md
│   │   ├── file-inventory.json
│   │   ├── DEPENDENCY-GRAPH.md
│   │   ├── DEPENDENCY-REPORT.json
│   │   ├── MODULE-OWNERSHIP.md
│   │   ├── module-registry.yaml
│   │   ├── DUPLICATE-ANALYSIS.md
│   │   ├── REPOSITORY-ARCHITECTURE.md
│   │   └── FINAL-DIRECTORY-STRUCTURE.md     (this file)
│   └── reports/
│       ├── AUSI-FULL-PROJECT-REAUDIT.md     # (pending)
│       └── AUSI-REPOSITORY-REORGANIZATION-FINAL-REPORT.md  # (pending)
│
├── scripts/
│   └── verify_terraform_plan.py      # (NEW)
│
├── Makefile                          # (modified: Terraform plan SHA-256 binding)
├── .gitmodules                       # (modified: HTTPS URLs only)
├── compose.open-webui.yml            # (modified: fail-closed auth)
└── AGENTS.md                         # Repository governance rules
```

## Key Changes Made (2026-11-05)

| File / Directory | Change Type | Issue |
|---|---|---|
| `.gitmodules` | Modified — HTTPS only | #382 |
| `.github/workflows/ci.yml` | Modified — SSH removed, HTTPS submodules | #382, #393 |
| `.github/workflows/billing-ledger-postgres.yml` | **NEW** | #346 |
| `Makefile` | Modified — Terraform plan SHA-256 | #384 |
| `compose.open-webui.yml` | Modified — fail-closed auth | #396 |
| `deploy/cloudflare/tunnel-ingress.yml` | Modified — PG removed | #399 |
| `infrastructure/kubernetes/base/*.yaml` | Modified — zcoder-api renamed | #377 |
| `infrastructure/terraform/cloudflare/zworkforce.tf` | Modified — PG route removed | #385, #399 |
| `packages/zider/server/app/*.py` | Modified — auth + CORS + tenant PDF | #397 |
| `packages/ztrader/zeaz-intelligence/src/ztrader_intel/*.py` | Modified — tenant isolation | #375 |
| `services/ai-gateway/index.js` | Modified — tenant rate-limit | #398 |
| `services/billing-ledger/server.mjs` | Modified — PG store | #346 |
| `services/billing-ledger/postgres-store.mjs` | **NEW** | #346 |
| `services/billing-ledger/migrations/001_*.sql` | **NEW** | #346 |
| `services/workspace-runtime/server.mjs` | Modified — four-eyes HMAC | #374 |
| `apps/zow/server.mjs` | Modified — operator token gate | #374 |
| `tests/test_repository_policy.py` | Modified — +k8s identity test | #377 |
| `tests/test_cloudflare_ingress.py` | Modified — +PG ingress test | #399 |
| `tests/test_submodule_security.py` | **NEW** | #382 |
| `tests/test_terraform_plan_approval.py` | **NEW** | #384 |
| `scripts/verify_terraform_plan.py` | **NEW** | #384 |
| `docs/security/OPEN-WEBUI-CUSTOMER-BOUNDARY.md` | **NEW** | #396 |
| `docs/security/PUBLIC-SUBMODULE-CHECKOUT.md` | **NEW** | #382 |
