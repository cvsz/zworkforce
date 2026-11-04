# ZWorkforce Duplicate Analysis

**Generated:** 2026-11-05 UTC+7  
**Baseline SHA:** `1249243958280c5499a564180d32f6677d8791ff`

> [!NOTE] ผลการวิเคราะห์นี้มาจาก `git ls-files` จริง ไม่ใช่การอนุมานจากเอกสาร

## Classification Summary

| Category | Count | Action |
|---|---|---|
| ✅ NORMAL — ไฟล์ชื่อซ้ำโดยธรรมชาติ (framework convention) | 183 | ไม่ต้องทำอะไร |
| ⚠️ MIRROR — packages/zarvis/ ahead of services/ | 3 services | Document ownership; sync เมื่อ deploy |
| 🔴 DEAD — บาคอัพและ scratch output ที่ไม่มี consumer | 4 files | Queue for removal in separate PR |
| 📋 REVIEW — zarvis/ apps mirror vs apps/ | 3 apps | Document canonical; ตรวจ Docker/CI refs |

## 1. Normal Duplicates (ไม่ต้องทำอะไร)

ชื่อซ้ำเหล่านี้เป็น convention ของ framework ที่ถูกต้อง:

| Filename | Copies | Reason |
|---|---|---|
| `route.ts` | 98 | Next.js App Router — each is a unique API endpoint at a unique path |
| `__init__.py` | 75 | Python package markers — required for each package |
| `README.md` | 67 | Per-module documentation |
| `SKILL.md` | 60 | Per-skill agent instruction files |
| `page.tsx` | 44 | Next.js App Router pages — each at a unique URL path |
| `package.json` | 42 | Per-package Node.js manifests (pnpm workspace) |
| `migration.sql` | 14 | Prisma sequential migrations (each is unique by timestamp-prefixed directory) |
| `AGENTS.md` | 7 | Per-subtree agent instructions (root rules apply; nested override specific subtree) |
| `.gitignore` | 8 | Per-package gitignore files |
| `.env.example` | 8 | Per-package environment examples |

## 2. Z.A.R.V.I.S. Service Mirrors (packages/zarvis/ vs services/)

**Canonical source: `packages/zarvis/services/`**

| Service | Status | Drift Summary |
|---|---|---|
| `zarvis-action-gateway` | ✅ Identical | No drift |
| `zarvis-memory` | ✅ Identical | No drift |
| `zarvis-perception` | ✅ Identical | No drift |
| `zarvis-proactive` | ✅ Identical | No drift |
| `zarvis-owner-voice-edge` | ✅ Identical | No drift |
| **zarvis-orchestrator** | ⚠️ packages/zarvis AHEAD | +`live_voice.mjs`, +`skill-catalog.mjs`, +`live_voice.test.mjs`, +`orchestrator-skill-execution.test.mjs`; `orchestrator.mjs` differs |
| **zarvis-task-gateway** | ⚠️ packages/zarvis AHEAD | +`durable-adapters.mjs`, +`orchestrator-core.mjs`; `runtime.mjs`, `server.mjs`, `README.md` all differ |
| **voice-agent** | ⚠️ packages/zarvis AHEAD | `healthcheck.py` has provider registry reporting + docstring (packages/zarvis has 9 extra lines) |

**Decision:** Keep `packages/zarvis/services/` as the development source. The `services/` mirrors are used for deployment references in `compose.yaml` and CI. When features advance in `packages/zarvis/`, sync to `services/` via PRs before deployment. No blind deletion.

## 3. Z.A.R.V.I.S. App Mirrors (packages/zarvis/apps/ vs apps/)

| App | packages/zarvis/apps/ | apps/ | Status |
|---|---|---|---|
| `zarvis-console` | ✅ exists | ✅ exists | Likely synchronized via workspace tooling |
| `zvoice` | ✅ exists | ✅ exists | Likely synchronized |
| `zarvis-windows` | ✅ exists | ✅ exists | Likely synchronized |

**Action needed:** Verify which path is referenced in `compose.zarvis-local.yml`, `compose.zarvis-owner-domain.yml`, and `.github/workflows/zarvis.yml` to confirm canonical source for deployment.

## 4. Dead Files (Confirmed Safe to Remove)

These files have no consumers in source, CI, or deployment references:

| File | Evidence of Safety |
|---|---|
| `packages/zeto/test.txt` | `git log` shows only 1 commit (accidental committed stdout). No grep match in repo. |
| `packages/zeto/test_out.txt` | Same as above. |
| `packages/zeto/test/operatorApi.integration.test.js.bak` | `.bak` extension. Node `--test` glob does not match. No grep reference. |
| `packages/zeto/test/operatorRuntime.integration.test.js.bak` | Same as above. |

**Recommended action:** Remove in a focused cleanup PR with message: `chore(zeto): remove dead test scratch output and backup files`.

## 5. server.mjs Copies (26 total)

Each `server.mjs` is a **different service entry point** in a different directory. All are legitimate:
- `apps/zarvis-console/server.mjs` — Zarvis Console web server
- `apps/zchat/server.mjs` — ZChat web server  
- `apps/zow/server.mjs` — ZOW workbench server (modified: four-eyes auth)
- `apps/zvoice/server.mjs` — ZVoice server
- `apps/zwallet/server.mjs` — ZWallet server
- `services/billing-ledger/server.mjs` — Billing ledger (modified: durable PG store)
- `services/workspace-runtime/server.mjs` — Workspace runtime (modified: four-eyes gate)
- `services/zarvis-*/server.mjs` — Z.A.R.V.I.S. microservice entry points
- `packages/zarvis/services/*/server.mjs` — Z.A.R.V.I.S. canonical copies

**No consolidation needed** — these are correctly separated by business domain.

## 6. Duplicate FastAPI Service Patterns (P1 from original audit)

The original audit flagged "FastAPI services ซ้ำ 3 ชุด". Investigation finds:
- `zworkforce/` — Python control plane (FastAPI + SQLite/PostgreSQL) → canonical
- `packages/ztrader/zeaz-intelligence/` — Intelligence sidecar (FastAPI) → different domain, different data
- `packages/zider/server/` — Browser companion BFF (FastAPI) → different domain

**Decision:** These are 3 separate bounded services, not duplicates. No consolidation warranted. Each has distinct business logic and data models.

## 7. ZARVIS Module Duplication (P1 from original audit)

Original finding: "ZARVIS modules ซ้ำระหว่าง root กับ packages/zarvis/"

**Current assessment:**
- `packages/zarvis/` = canonical ZARVIS platform (workspace, services, apps, tools)
- `services/zarvis-*` = deployment-synced copies (some behind canonical)
- `apps/zarvis-*` = deployment-synced copies

**Root cause:** The monorepo uses `packages/zarvis/` as the development workspace and deploys service copies to `services/` and `apps/`. This is a valid monorepo pattern. The issue is the drift between canonical and deployed copies for 3 services.

**Resolution:** Document ownership (done in MODULE-OWNERSHIP.md). Do not delete `services/` copies until deployment references are migrated to `packages/zarvis/` paths.
