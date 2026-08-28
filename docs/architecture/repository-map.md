# Repository Map

## Top-level structure

| Path | Purpose |
|---|---|
| `apps/` | User-facing products and thin BFF/proxy surfaces |
| `services/` | Independently deployable APIs, workers, and runtime boundaries |
| `packages/` | Shared libraries and versioned contracts |
| `workers/` | Cloudflare Worker runtime |
| `tools/` | Developer tooling, generators, and operations checks |
| `scripts/` | Validation, CI, smoke, backup, rotation, and release scripts |
| `deploy/` | Dockerfiles and container build assets |
| `docs/` | Architecture, requirements, migration, runbooks, operations, security |
| `infrastructure/` | Kubernetes manifests, Cilium config, Terraform |
| `schemas/` | JSON schemas for operations and release artifacts |
| `tests/` | Root-level integration tests |
| `.github/` | CI workflows, CodeQL, Dependabot, issue/PR templates, release templates |
| `agents/` | Agent persona definitions (legacy surface) |
| `.agents/` | Auto-generated Kilo/Claude skill |
| `.claude/` | Claude commands, identity, and skill |
| `.codex/` | Codex CLI agents, prompts, config, suite manifest |
| `ai/` | AI provider catalog references |
| `configs/` | Non-secret configuration examples |
| `ops/` | Operational bundles (zarvis-owner-domain) |
| `zarvis-live-evidence/` | Live evidence bundles (operational artifact) |
| `zarvis-owner-domain-bundle/` | Owner-domain bundle artifacts |

## Apps

| App | Runtime | Owner | Purpose |
|---|---|---|---|
| `apps/agent-control-panel` | Next.js | Platform | Agent control UI |
| `apps/zaicoder` | Python backend + Node web | Platform | Coding agent backend and web surface |
| `apps/zarvis-console` | Node HTTP | Platform | Owner console for Zarvis orchestrator |
| `apps/zarvis-windows` | PowerShell installer | Platform | Windows client installer |
| `apps/zchat` | Node HTTP | Platform | Chat UI and gateway proxy |
| `apps/zeaz-web` | Cloudflare Worker | Platform | Legacy web surface |
| `apps/zow` | Node HTTP | Platform | Workspace operations UI and proxy |
| `apps/zvoice` | Node HTTP + Web Audio | Platform | Voice UI and local conversation fallback |
| `apps/zwallet` | Node HTTP | Platform | Billing-ledger adapter (billing only) |

## Services

| Service | Runtime | Owner | Purpose |
|---|---|---|---|
| `services/ai-gateway` | Node/Express | Platform | Upstream AI provider boundary, model catalog, streaming, usage emission |
| `services/agent-orchestrator` | Node HTTP | Platform | Durable agent jobs, approval, queue, retry, cancellation |
| `services/agent-provider` | Node HTTP | Platform | Durable state backend for agent jobs, queue, audit, workspaces, backup/restore |
| `services/billing-ledger` | Node HTTP | Platform | Immutable usage records, credits, invoice intents |
| `services/workspace-runtime` | Node HTTP | Platform | Project validation, shell/deploy approval boundary |
| `services/voice-gateway` | Node HTTP + TCP proxy | Platform | WebSocket ticket gateway for voice sessions |
| `services/voice-agent` | Python | Platform | Local Hugging Face speech pipeline |
| `services/phase6-api` | Python/FastAPI | Platform | External staging verification, Supabase read bridge |
| `services/z-prov` | Python | Platform | Provider management, control adapters, sandbox egress, enterprise vault |
| `services/zc` | Python/FastAPI | Platform | ZC API, CLI, webapp, cache, search, skills, gRPC, workers |
| `services/zarvis-orchestrator` | Node HTTP | Platform | Zarvis command execution, durable sessions |
| `services/zarvis-task-gateway` | Node HTTP | Platform | Zarvis task plans, approval, pause/resume/cancel/retry |
| `services/zarvis-memory` | Node HTTP | Platform | Encrypted memory store, proposals, corrections |
| `services/zarvis-action-gateway` | Node HTTP | Platform | Local action preview, approve, rollback, execute |
| `services/zarvis-proactive` | Node HTTP | Platform | Local proactive scheduler, subscriptions, notifications |
| `services/zarvis-perception` | Node HTTP | Platform | Encrypted perception sessions, media analysis |
| `services/zarvis-owner-voice-edge` | Node HTTP | Platform | Owner voice edge secret injection |
| `services/zarvis-owner-domain` | (compose-only) | Platform | Owner domain edge runtime |

## Packages

| Package | Purpose |
|---|---|
| `packages/contracts` | Versioned API and event schemas, compatibility tests |

## Tools

| Tool | Purpose |
|---|---|
| `tools/zctl` | Go CLI for platform operations |
| `tools/zai-factory` | Project generator and skills registry validator |
| `tools/ops` | SBOM generation, provenance verification, dependency checks |
| `tools/z-platform-cloudflare-py-installer` | Cloudflare Terraform provider installer |

## Workers

| Worker | Purpose |
|---|---|
| `workers/agent-control-worker` | Cloudflare Worker for agent control |

## CI

| Workflow | Purpose |
|---|---|
| `.github/workflows/ci.yml` | Node workspace tests, Python tests, Compose build, deployed smoke, SBOM |
| `.github/workflows/validate.yml` | Secret scan, browser credential isolation, Node tests, Python tests, Compose validate/build, deployed smoke, SBOM |
| `.github/workflows/codeql.yml` | CodeQL analysis |
| `.github/workflows/container-images.yml` | Container image build and push |
| `.github/workflows/deploy-production.yml` | Production deployment |
| `.github/workflows/deploy-zeaz-web.yml` | Zeaz-web deployment |
| `.github/workflows/external-staging-readiness.yml` | External staging verification |
| `.github/workflows/final-release-readiness.yml` | Release readiness gate |
| `.github/workflows/operations.yml` | Operations automation |
| `.github/workflows/phase6-external-suite.yml` | Phase 6 external suite |
| `.github/workflows/readiness-tooling.yml` | Readiness tooling |
| `.github/workflows/terraform-cloudflare.yml` | Terraform Cloudflare apply |
| `.github/workflows/validate-release-evidence.yml` | Release evidence validation |
| `.github/workflows/zarvis-local.yml` | Zarvis local CI |
| `.github/workflows/zarvis-local-release.yml` | Zarvis local release |
| `.github/workflows/zarvis-windows.yml` | Windows client CI |
| `.github/workflows/zctl.yml` | zctl CLI CI |

## Deployment assets

| Asset | Purpose |
|---|---|
| `deploy/docker/ai-gateway.Dockerfile` | AI Gateway container |
| `deploy/docker/node-service.Dockerfile` | Generic Node service container |
| `deploy/docker/next-service.Dockerfile` | Next.js service container |
| `services/zc/Dockerfile` | ZC Python service container |
| `services/voice-agent/Dockerfile` | Voice agent Python container |
| `services/voice-gateway/Dockerfile` | Voice gateway container |
| `compose.yml` | Main local stack |
| `compose.voice.yml` | Voice overlay |
| `compose.zarvis-local.yml` | Zarvis local overlay |
| `compose.zarvis-owner-domain.yml` | Owner domain overlay |
| `compose.zarvis-owner-voice.yml` | Owner voice overlay |
| `docker-compose.phase6.yml` | Phase 6 external stack |
| `infrastructure/kubernetes/` | K8s deployments, network policies, Cilium, ArgoCD |
| `infrastructure/terraform/` | Cloudflare Terraform |

## Migration sources

| Source repo | Migrated into | Status |
|---|---|---|
| `/home/cvsz/zc` | `services/zc` | Migrated — implementation merged |
| `/home/cvsz/zcoder` | `services/zc` | Consolidated — same product as zc |
| `/home/cvsz/z-prov` | `services/z-prov` | Migrated — new service added |
| `/home/cvsz/zai-coder` | `apps/zaicoder` | Partial — core backend migrated; full repo remains migration source of record |
| `/home/cvsz/zaff` | Not merged | Separate product (Affiliate Automation OS) |
| `/home/cvsz/zworkforce` | Not merged | Separate product (Enterprise AI Workforce OS) |
| `/home/cvsz/zeaz` | Not merged | Migration source of record per z-platform README |
| `/home/cvsz/zeaz-ai-command-center` | Not merged | Separate product |
| `/home/cvsz/zeaz-autonomous-security-agent` | Not merged | Separate product |
| `/home/cvsz/zeaz-one-complete` | Not merged | Product plan artifacts |
| `/home/cvsz/zeto` | Not merged | Separate product (AI Content Factory) |
| `/home/cvsz/zkid` / `/home/cvsz/zkids-zai` | Not merged | Separate products (kids apps) |
| `/home/cvsz/zknowbase` | Not merged | Separate product (knowledge base) |
| `/home/cvsz/zloop_orig` | Not merged | Small skills repo |
| `/home/cvsz/zpay-android` | Not merged | Android app |
| `/home/cvsz/zpwsh` | Not merged | PowerShell module |
| `/home/cvsz/zwiki` | Not merged | Wiki |
| `/home/cvsz/z-world` | Not merged | Separate platform (OCU/World) |
| `/home/cvsz/zaffiliate` | Not merged | Separate product (affiliate marketing) |
| `/home/cvsz/zdash` | Not merged | Referenced as submodule in z-platform |

| Surface | Purpose |
|---|---|
| `.agents/skills/z-platform/SKILL.md` | Auto-generated Kilo skill |
| `.claude/skills/z-platform/SKILL.md` | Auto-generated Claude skill (identical to .agents) |
| `.claude/commands/` | Claude slash commands |
| `.claude/identity.json` | Claude identity profile |
| `.claude/ecc-tools.json` | ECC tool config |
| `.codex/AGENTS.md` | Codex ECC baseline |
| `.codex/config.toml` | Codex MCP config |
| `.codex/agents/` | Codex agent definitions |
| `.codex/prompts/` | Codex phase prompts |
| `.codex/suite/` | Master meta cloud suite |
| `agents/` | 60+ agent persona definitions |

## Environment files

| File | Purpose |
|---|---|
| `.env.example` | Canonical local environment template |
| `.env` | Local runtime secrets (git-ignored) |
| `.env.zarvis.local` | Zarvis local overrides |
| `.env.zarvis.voice.local` | Zarvis voice overrides |
| `.env.zarvis.voice.local.bak` | Backup of voice overrides |
