# ZWorkforce File Inventory

**Generated:** 2026-11-05T05:32 UTC+7  
**Baseline SHA:** `1249243958280c5499a564180d32f6677d8791ff`  
**Total Tracked Files:** 3,092  

> [!NOTE] Machine-readable details are in [`file-inventory.json`](./file-inventory.json). This document is a human-readable summary.

## Top-Level Directory Summary

| Directory | File Count | Description |
|---|---|---|
| `packages/` | 1,659 | Packages: zarvis, zider, ztrader, zeto, zsp-aitool, zksato, zok, zmovie, zttshop-php, wall-street, contracts |
| `services/` | 489 | Microservices: ai-gateway, billing-ledger, workspace-runtime, zarvis-*, zc, zc-api, voice-* |
| `apps/` | 165 | Applications: zarvis-console, zchat, zow, zvoice, zwallet, zaicoder, zeaz-web, agent-control-panel, frontend |
| `zworkforce/` | 137 | Core Python control plane (Python package — the canonical service entry point) |
| `tests/` | 132 | Repository-level policy and integration tests |
| `docs/` | 103 | Documentation, architecture, security, planning reports |
| `.agents/` | 82 | AI Agent skill definitions (Gemini CLI, MCP, zeaz-* skills) |
| `ZWorkforceClient/` | 53 | Windows native WinUI client (C#/.NET) |
| `scripts/` | 53 | Operational scripts: release, verify, automation, deployment |
| `infrastructure/` | 44 | Kubernetes manifests, Terraform (Cloudflare) |
| `deploy/` | 40 | Docker, Caddy, Cloudflare tunnel configurations |
| `planning/` | 25 | Release and feature planning documents |
| `.github/` | 24 | GitHub Actions workflows, rulesets, CODEOWNERS |
| `examples/` | 14 | Usage examples |
| `schemas/` | 11 | JSON/YAML schemas |
| `plugins/` | 5 | Plugin artifacts |
| `backups/` | 5 | Backup reference files |

## Extension Breakdown

| Extension | Count | Primary Use |
|---|---|---|
| `.py` | 687 | Python (control plane, tests, scripts) |
| `.md` | 632 | Documentation and agent skill instructions |
| `.ts` | 421 | TypeScript (frontend, zsp-aitool Next.js) |
| `.json` | 196 | Configuration, schemas, package manifests |
| `.mjs` | 172 | Node.js ES modules (services, apps) |
| `.js` | 169 | JavaScript (services, legacy, public assets) |
| `.tsx` | 139 | React/TypeScript components |
| `.sh` | 121 | Shell scripts |
| `.yaml` | 77 | Infrastructure, CI, Kubernetes, Cloudflare |
| `.yml` | 76 | GitHub Actions workflows, Compose files |
| `.sql` | 30 | Database migrations |
| `.cs` | 46 | C# Windows client |
| `.css` | 34 | Stylesheets |
| `.html` | 30 | Static HTML pages |

## Duplicate Filename Analysis

**Files with duplicate basenames across different directories: 227**

The most significant categories are:

| Filename | Copies | Classification |
|---|---|---|
| `route.ts` | 98 | ✅ NORMAL — Next.js App Router API routes (each is a unique endpoint) |
| `__init__.py` | 75 | ✅ NORMAL — Python package markers |
| `README.md` | 67 | ✅ NORMAL — per-module documentation |
| `SKILL.md` | 60 | ✅ NORMAL — per-skill agent instruction files |
| `page.tsx` | 44 | ✅ NORMAL — Next.js App Router pages |
| `package.json` | 42 | ✅ NORMAL — per-package Node.js manifests |
| `server.mjs` | 26 | ⚠️ REVIEW — multiple service entry points, some have zarvis/ mirror copies |
| `Dockerfile` | 16 | ⚠️ REVIEW — multiple build targets; zarvis/ mirrors top-level services/ |
| `styles.css` | 16 | ⚠️ REVIEW — zarvis/ mirrors apps/ static assets |
| `runtime.mjs` | 10 | ⚠️ REVIEW — zarvis/ service mirrors have extra features vs services/ |
| `AGENTS.md` | 7 | ✅ NORMAL — per-subtree agent instructions (root overrides nested) |

> [!IMPORTANT] The `packages/zarvis/` subdirectory contains canonical copies of several services that have **advanced further** than their `services/` counterparts. See [`DUPLICATE-ANALYSIS.md`](./DUPLICATE-ANALYSIS.md) for the drift analysis and [`MODULE-OWNERSHIP.md`](./MODULE-OWNERSHIP.md) for canonical ownership.

## File Provenance

All file counts are from `git ls-files` on the working tree as of baseline SHA `1249243958280c5499a564180d32f6677d8791ff` plus the security/governance remediation commits currently in the working tree (not yet pushed).

Untracked files preserved per AGENTS.md:
- `docs/MASTER-PROMPT-031126.md` (operator prompt artifact)
