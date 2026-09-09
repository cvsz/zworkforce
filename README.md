# zWorkforce

**Enterprise AI Workforce Operating System and ZEAZ AI monorepo — governed agents, workflows, provider routing, apps, realtime voice, developer workspaces, automation, AI FinOps, and production evidence.**

[![CI](https://github.com/cvsz/zworkforce/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/cvsz/zworkforce/actions/workflows/ci.yml)
[![CodeQL](https://github.com/cvsz/zworkforce/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/cvsz/zworkforce/actions/workflows/codeql.yml)
[![Dependency Review](https://github.com/cvsz/zworkforce/actions/workflows/dependency-review.yml/badge.svg)](https://github.com/cvsz/zworkforce/actions/workflows/dependency-review.yml)
[![Validate](https://github.com/cvsz/zworkforce/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/cvsz/zworkforce/actions/workflows/validate.yml)
[![HA Infrastructure](https://github.com/cvsz/zworkforce/actions/workflows/ha-infrastructure.yml/badge.svg?branch=main)](https://github.com/cvsz/zworkforce/actions/workflows/ha-infrastructure.yml)
[![Readiness Tooling](https://github.com/cvsz/zworkforce/actions/workflows/readiness-tooling.yml/badge.svg?branch=main)](https://github.com/cvsz/zworkforce/actions/workflows/readiness-tooling.yml)
[![Release Evidence](https://github.com/cvsz/zworkforce/actions/workflows/validate-release-evidence.yml/badge.svg?branch=main)](https://github.com/cvsz/zworkforce/actions/workflows/validate-release-evidence.yml)
[![Operations](https://github.com/cvsz/zworkforce/actions/workflows/operations.yml/badge.svg?branch=main)](https://github.com/cvsz/zworkforce/actions/workflows/operations.yml)
[![Terraform Cloudflare](https://github.com/cvsz/zworkforce/actions/workflows/terraform-cloudflare.yml/badge.svg?branch=main)](https://github.com/cvsz/zworkforce/actions/workflows/terraform-cloudflare.yml)
[![API Key Tools](https://github.com/cvsz/zworkforce/actions/workflows/apikey-tools.yml/badge.svg?branch=main)](https://github.com/cvsz/zworkforce/actions/workflows/apikey-tools.yml)
[![zctl](https://github.com/cvsz/zworkforce/actions/workflows/zctl.yml/badge.svg?branch=main)](https://github.com/cvsz/zworkforce/actions/workflows/zctl.yml)
[![ZARVIS Local](https://github.com/cvsz/zworkforce/actions/workflows/zarvis-local.yml/badge.svg?branch=main)](https://github.com/cvsz/zworkforce/actions/workflows/zarvis-local.yml)
[![ZARVIS Local Release](https://github.com/cvsz/zworkforce/actions/workflows/zarvis-local-release.yml/badge.svg?branch=main)](https://github.com/cvsz/zworkforce/actions/workflows/zarvis-local-release.yml)
[![ZARVIS Windows](https://github.com/cvsz/zworkforce/actions/workflows/zarvis-windows.yml/badge.svg?branch=main)](https://github.com/cvsz/zworkforce/actions/workflows/zarvis-windows.yml)
![Release](https://img.shields.io/badge/release-v3.0.4%20candidate-orange)
![Python](https://img.shields.io/badge/python-3.12%E2%80%933.14-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Commit Signing](https://img.shields.io/badge/commit%20signing-GPG%20required-blue)
![Production Evidence](https://img.shields.io/badge/production%20evidence-external%20gates%20pending-orange)

zWorkforce combines a Python control plane with a JavaScript/TypeScript monorepo, native Windows clients, Go/operator tooling, Cloudflare infrastructure, and specialized ZEAZ product packages. The core control plane turns one or more model endpoints into a governed AI workforce: tenants submit work to named agents; model routing selects cost/quality tiers; workers claim durable tasks; approvals and policy-as-code gate risky actions; workflows, schedules, and events compose automation; memory and artifacts preserve context; and FinOps/SLO telemetry measures cost and outcomes.

## Status and release truth

Repository version: **3.0.4**.

`v3.0.4` is a **corrective release candidate**, not a claim that every external production gate is complete. GitHub Actions validate source, tests, packaging, security contracts, and repository-controlled deployment logic. Real HA failover, disaster recovery, external storage, alert delivery, trusted Windows signing, exact-candidate production deployment, and other environment-owned controls require durable operator evidence before a production GO decision.

See [`docs/PRODUCTION-EVIDENCE.md`](docs/PRODUCTION-EVIDENCE.md) for the authoritative evidence ledger.

## v3.0.4 highlights

- Security hardening across tenant-scoped uploads, gRPC, provider gateways, SSRF/redirect handling, credential isolation, and deployment validation.
- Consolidated application, service, and package architecture with explicit responsibility and security boundaries.
- Exact-candidate release governance, external-readiness tooling, restore verification, and durable evidence workflows.
- Expanded full-repository documentation with live workflow status badges and explicit environment-evidence boundaries.

| Marker | Meaning |
| --- | --- |
| **Implemented** | Functional implementation exists in the repository and has a defined validation path. |
| **Partial** | Useful implementation exists, but migration, integration, or product scope remains incomplete. |
| **Sandbox** | Hardened local/developer implementation; not a production or Gold Master claim. |
| **External evidence** | Repository code exists, but production status requires operator-run environment evidence. |
| **Boundary** | Deliberately constrained component that must not acquire authority outside its stated role. |
| **Submodule** | Separate repository pinned into this monorepo. |

## Repository at a glance

| Area | Inventory | Purpose |
| --- | ---: | --- |
| Core Python package | 1 | Multi-tenant AI workforce control plane, worker, scheduler, policy, memory, artifacts, MCP, FinOps. |
| `apps/` | 10 top-level apps | Chat, voice, workspace, web, Windows/operator and UI surfaces. |
| Root native client | 1 | `ZWorkforceClient/` Windows operator client for the core REST control plane. |
| `packages/` | 9 entries | 7 in-tree product/shared packages plus 2 Git submodules. |
| `services/` | 18 top-level services | Agent, AI gateway, voice, workspace, billing, ZARVIS, provider and zc services. |
| `tools/` | 6 tool groups | Prompt generation, operations, installers, factory tooling and zctl. |
| Root orchestration | `control.sh`, `cmd/zctl/` | Lifecycle, diagnostics, orchestration and operator CLI. |
| Infra / delivery | `deploy/`, `infrastructure/`, `.github/workflows/` | Docker, Kubernetes, Cloudflare, CI/CD, security and release evidence. |

The JavaScript workspace is intentionally unified across `apps/*`, `services/*`, and `packages/*` via pnpm workspaces. `packages/zksato` and `packages/zttshop-php` are pinned Git submodules.

## Core capabilities

| Domain | Capability | Repository status |
| --- | --- | --- |
| Agent control plane | tenants, agents, immutable agent versions, durable task lifecycle | **Implemented** |
| Authorization | RBAC/scopes, tenant context, four-eyes approval, policy-as-code | **Implemented** |
| Distributed runtime | PostgreSQL task leasing with `FOR UPDATE SKIP LOCKED`, heartbeats, retries, dead-letter state | **Implemented**; HA behavior still needs final external evidence |
| Local runtime | SQLite/WAL zero-config development backend | **Implemented** |
| Automation | workflow DAGs, cron/interval schedules, durable event triggers, dedupe | **Implemented** |
| HA coordination | scheduler/outbox service leases and leader-aware execution | **Implemented**; final dual-replica evidence pending |
| Model routing | Luna/Terra/Sol tiers, provider pools, health, failover/circuit behavior | **Implemented** |
| Evaluation | A/B model/tier suites with quality, cost and outcome comparison | **Implemented** |
| Memory / RAG | local semantic vectors or Qdrant plus OpenAI-compatible embeddings | **Implemented** |
| Artifacts | content-addressed local or S3-compatible storage | **Implemented**; target external storage evidence is environment-owned |
| Identity | native OIDC/JWKS plus signed identity-aware proxy boundary | **Implemented** |
| Secrets | environment, mounted files, AWS Secrets Manager and Vault KV v2 references | **Implemented** |
| MCP | authenticated stateless MCP endpoint and client tooling | **Implemented** |
| Observability | health/readiness, Prometheus, OTLP, Grafana examples, audit correlation | **Implemented**; external alert/trace evidence tracked separately |
| AI FinOps | budgets, chargeback/showback, cost per outcome, capacity and SLO evaluation | **Implemented** |
| Deployment | Docker, Compose, Kubernetes, PDB/HPA/network policy, Cloudflare tooling | **Implemented**; production topology is operator-owned |
| Security | bounded tools, SSRF/path confinement, credential isolation, audit chains, CodeQL/dependency review | **Implemented** repository controls |

## Architecture

```text
Browser / Windows / CLI / MCP / OIDC clients
                    |
                    v
+---------------------------------------------------------------+
|                     zWorkforce surfaces                       |
| ZChat | ZVoice | ZOW | ZARVIS | ZEAZ Web | operator clients  |
+-------------------------------+-------------------------------+
                                |
                                v
+---------------------------------------------------------------+
|                 Control plane + service mesh                  |
| tenants | RBAC | agents | approvals | policy | workflows      |
| scheduler | events | evaluation | memory | artifacts | FinOps |
| AI gateway | agent orchestrator | workspace runtime | billing |
+-------------------------------+-------------------------------+
                                |
              +-----------------+------------------+
              |                                    |
              v                                    v
+---------------------------+       +----------------------------+
| Durable execution/data    |       | AI / tool boundaries       |
| SQLite / PostgreSQL       |       | providers / z-prov         |
| queues / leases / outbox  |       | sandbox / HTTP / shell     |
| Qdrant / S3-compatible    |       | voice / ZARVIS services    |
+---------------------------+       +----------------------------+
              |                                    |
              +-----------------+------------------+
                                v
                 OTLP / Prometheus / Grafana
                 Cloudflare / Kubernetes / CI
```

Detailed design is documented in [`ARCHITECTURE.md`](ARCHITECTURE.md), [`SECURITY.md`](SECURITY.md), and [`docs/architecture/`](docs/architecture/).

## Applications

### Top-level `apps/`

| App | Role | Status / boundary |
| --- | --- | --- |
| [`agent-control-panel`](apps/agent-control-panel/) | Next.js provider/key-pool control-panel UI scaffold. | **Partial / prototype** — current form simulates persistence client-side; do not treat it as a real secret-management surface. |
| [`frontend`](apps/frontend/) | UI/UX development stack containing ReUI dashboard, Canva App UI Kit, MetricUI analytics and Canva MCP workspaces. | **Partial / development stack** |
| [`zaicoder`](apps/zaicoder/) | Coding-agent application whose browser/CLI traffic is designed to route through the AI Gateway. | **Partial migration** — app/package/gateway contracts exist; legacy runtime/web import remains dependency-audited work. |
| [`zarvis-console`](apps/zarvis-console/) | Private browser command center for Z.A.R.V.I.S. | **Implemented boundary** — owner-only, trusted-edge gated, no provider/service secrets in browser code. |
| [`zarvis-windows`](apps/zarvis-windows/) | Native Windows 11 Z.A.R.V.I.S. operator client using local SSH forwarding. | **Implemented build/package path**; trusted production signing remains external evidence. |
| [`zchat`](apps/zchat/) | Gateway-only conversation client with streaming, history, titles, system prompts, templates, export, theme, retry and cancellation. | **Implemented**; deployed identity/accessibility/mobile evidence remains environment-owned. |
| [`zeaz-web`](apps/zeaz-web/) | ZEAZ public web + ZEAZ One early-access surface. | **Implemented full stack** — Cloudflare Worker, D1, public early-access API, protected admin API, bilingual legal pages. |
| [`zow`](apps/zow/) | User-facing workspace/proxy. | **Implemented boundary** — shell/deploy execution belongs to `workspace-runtime` and stays approval-gated. |
| [`zvoice`](apps/zvoice/) | Browser realtime voice surface using signed WebSocket tickets and AudioWorklet PCM streaming. | **Implemented** — supports private Z.A.R.V.I.S. owner mode and interruption. |
| [`zwallet`](apps/zwallet/) | Billing-ledger adapter for credits and invoice intents. | **Implemented boundary** — intentionally has **no** wallet signing, swaps, cards, KYC, MPC or private-key authority. |

### Root Windows client

[`ZWorkforceClient/`](ZWorkforceClient/) is the native Windows operator client for the core zWorkforce REST control plane. It is separate from the owner-only Z.A.R.V.I.S. Windows application and has its own Windows CI/package path.

## Product and shared packages

| Package | Role | Status / boundary |
| --- | --- | --- |
| [`contracts`](packages/contracts/) | Versioned cross-service request/event/error contracts such as `ai.chat.request.v1` and agent lifecycle events. | **Foundational / evolving** |
| [`wall-street`](packages/wall-street/) | TradingView interoperability + Binance/KuCoin public realtime market intelligence. | **Implemented boundary** — market intelligence only; no exchange order execution or trading credentials. |
| [`zarvis`](packages/zarvis/) | Consolidated Z.A.R.V.I.S. suite: surfaces, orchestration, memory, perception, proactive context, voice and operations. | **Implemented multi-component suite** with separate external release evidence where required. |
| [`zeto`](packages/zeto/) | AI content/publishing automation. Current implementation includes Facebook dashboard, compose, queue, scheduler, feed, history, analytics and AI-generation entry point. | **Partial** — end-to-end `IDEATE → ... → LEARN` Content Factory is target architecture, not a blanket completion claim. |
| [`zider`](packages/zider/) | Browser AI sidebar/companion with multi-model chat, web grounding, translation, writing, voice, vision/OCR, ChatPDF, artifacts and zWorkforce bridge. | **Implemented package surface** with its own tests. |
| [`zok`](packages/zok/) | Vite/React + Express conversational-commerce workspace. | **Sandbox / not Gold Master** — local inbox/agent/flow/analytics/auth controls exist; real external channel delivery, durable multi-tenancy, enterprise RBAC/billing/SLO evidence remain separate work. |
| [`zsp-aitool`](packages/zsp-aitool/) | Thai-first Shopee Affiliate SaaS + HyperFrames video composition/render operations. | **Implemented large product surface**; production render workers and environment checks are operator-controlled. |
| [`zksato`](packages/zksato) | External project integrated as a pinned Git submodule. | **Submodule** |
| [`zttshop-php`](packages/zttshop-php) | External PHP project integrated as a pinned Git submodule. | **Submodule** |

## Services

### Core platform services

| Service | Responsibility | Status / boundary |
| --- | --- | --- |
| [`agent-orchestrator`](services/agent-orchestrator/) | Asynchronous job lifecycle, approval, scoped execution, retry/cancel and audit correlation. | **Implemented**; external production adapters require explicit operator enablement. |
| [`agent-provider`](services/agent-provider/) | Node agent-provider service boundary. | **Implemented service workspace** with start/test contract. |
| [`ai-gateway`](services/ai-gateway/) | Server-side model gateway, provider key rotation/pooling and OpenAI/Anthropic-compatible request paths. | **Implemented security boundary** — provider credentials stay server-side. |
| [`billing-ledger`](services/billing-ledger/) | Billing/credits ledger boundary consumed by ZWallet and platform services. | **Implemented service boundary** |
| [`workspace-runtime`](services/workspace-runtime/) | Isolated generated-project validation plus approval-gated shell/deploy requests. | **Implemented execution boundary** |
| [`z-prov`](services/z-prov/) | Standalone multi-provider gateway supporting Anthropic Messages, OpenAI Chat/Responses, aliases, local/free fallbacks, auth and rate limiting. | **Release candidate service** (`0.4.0rc1` line documented in-package). |

### Consolidation / compatibility services

| Service | Responsibility | Status |
| --- | --- | --- |
| [`phase6-api`](services/phase6-api/) | Phase 6 compatibility / verification service retained in the source tree. | **Compatibility surface** — current consolidated production deployment treats `zc-api` as the canonical K8s service rather than probing a separate `phase6-api` workload. |
| [`zc-api`](services/zc-api/) | Consolidated zc / staging-verification API service identity. | **Implemented deployment service** |
| [`zc`](services/zc/) | Python zcoder API/CLI/webapp stack with upload, AI/chat/resource/control-panel and gRPC surfaces. | **Implemented large service**; protected operations are authenticated and tenant scoped. |

### Realtime voice services

| Service | Responsibility | Status |
| --- | --- | --- |
| [`voice-gateway`](services/voice-gateway/) | Short-lived realtime voice/WebSocket ticket gateway and server-side voice routing boundary. | **Implemented** |
| [`voice-agent`](services/voice-agent/) | Speech/voice agent processing boundary used by the realtime stack. | **Implemented / environment-dependent providers** |

### Z.A.R.V.I.S. services

| Service | Responsibility | Status |
| --- | --- | --- |
| [`zarvis-action-gateway`](services/zarvis-action-gateway/) | Local action gateway and worker boundary. | **Implemented local hardened service** |
| [`zarvis-memory`](services/zarvis-memory/) | Durable owner memory/context service. | **Implemented** |
| [`zarvis-orchestrator`](services/zarvis-orchestrator/) | Command orchestration and audited action routing. | **Implemented** |
| [`zarvis-owner-voice-edge`](services/zarvis-owner-voice-edge/) | Private owner voice-edge integration. | **Implemented boundary** |
| [`zarvis-perception`](services/zarvis-perception/) | Perception/context ingestion service. | **Implemented package service** |
| [`zarvis-proactive`](services/zarvis-proactive/) | Proactive scheduler/suggestion service and worker. | **Implemented local hardened service** |
| [`zarvis-task-gateway`](services/zarvis-task-gateway/) | Task bridge/gateway for Z.A.R.V.I.S. execution. | **Implemented service boundary** |

## Tooling and operator surfaces

| Path | Purpose |
| --- | --- |
| [`tools/agent_prompt_generator/`](tools/agent_prompt_generator/) | Agent prompt generation tooling. |
| [`tools/ops/`](tools/ops/) | Dependency, SBOM, provenance and operational tooling. |
| [`tools/scripts/`](tools/scripts/) | Host/recovery/migration/admin scripts. |
| [`tools/z-platform-cloudflare-py-installer/`](tools/z-platform-cloudflare-py-installer/) | Cloudflare/Terraform installer tooling. |
| [`tools/zai-factory/`](tools/zai-factory/) | Template, skill and service-generation factory. |
| [`tools/zctl/`](tools/zctl/) | zctl tool workspace. |
| [`cmd/zctl/`](cmd/zctl/) | Root Go zctl command implementation. |
| [`control.sh`](control.sh) | Root lifecycle/orchestration script. |

Repo-local agent instructions and skills live under [`.agents/`](.agents/), [`.claude/`](.claude/), and [`.codex/`](.codex/). ProMeta master operating documentation is in [`docs/PROMETA-MASTER.md`](docs/PROMETA-MASTER.md), with runtime-ready seed catalogs in [`examples/prometa-agent-catalog.json`](examples/prometa-agent-catalog.json), [`examples/prometa-skills.json`](examples/prometa-skills.json), [`examples/prometa-agent-templates.json`](examples/prometa-agent-templates.json), and [`examples/prometa-workflows.json`](examples/prometa-workflows.json).

## Quick start — core Python control plane

Requirements: Python **3.12+**.

```bash
git clone --recurse-submodules https://github.com/cvsz/zworkforce.git
cd zworkforce
cp .env.example .env
python -m pip install .
make check
python -m zworkforce serve
```

Open the local control-plane endpoint documented by the runtime. `make check` runs the repository Python tests, doctor, release integrity, shell checks and static security invariants.

Common commands:

```bash
make test
make doctor
make release-check
make lint-security
make docker-build

python -m zworkforce worker
python -m zworkforce scheduler --once
```

A real PostgreSQL integration gate is available separately:

```bash
export ZWORKFORCE_TEST_POSTGRES_URL='postgresql://...'
make postgres-test
```

## JavaScript / TypeScript monorepo

The root workspace spans `apps/*`, `services/*`, and `packages/*`. Individual products have their own runtime and test commands; do not assume one Node version or deployment model applies to every package.

```bash
corepack enable
pnpm install --ignore-scripts
```

For a focused workspace, follow that component's README and package scripts, for example:

```bash
npm test --prefix apps/zchat
npm test --prefix services/agent-orchestrator
npm test --prefix services/workspace-runtime
```

## Compose and local service stacks

The repository intentionally has multiple Compose boundaries:

| File | Scope |
| --- | --- |
| [`compose.yaml`](compose.yaml) | Core zWorkforce/PostgreSQL production-shaped stack and optional integration services. |
| [`services-compose.yml`](services-compose.yml) | Consolidated platform service development/smoke stack. |
| [`zarvis-local-compose.yml`](zarvis-local-compose.yml) | Hardened loopback/local Z.A.R.V.I.S. action + proactive stack. |
| [`compose.zsp-aitool.yml`](compose.zsp-aitool.yml) | ZSP AI Tool integration stack. |
| [`compose.open-webui.yml`](compose.open-webui.yml) | Optional Open WebUI integration. |

Example core stack:

```bash
export ZWORKFORCE_POSTGRES_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export ZWORKFORCE_API_KEYS="$(python -c 'import secrets; print(secrets.token_urlsafe(32))'):superadmin:default:bootstrap:*"
docker compose up -d --build
```

Example consolidated service validation:

```bash
Z_PLATFORM_SERVICE_TOKEN=local-test-token \
ZC_API_TOKEN=local-test-token \
  docker compose -f services-compose.yml config --quiet
```

Example local Z.A.R.V.I.S. setup:

```bash
bash scripts/zarvis-local-setup.sh
```

## Kubernetes and infrastructure

Core Kubernetes resources are under [`deploy/kubernetes/`](deploy/kubernetes/) and consolidated platform resources under [`infrastructure/kubernetes/`](infrastructure/kubernetes/). Cloudflare/Terraform configuration is under [`infrastructure/terraform/`](infrastructure/terraform/).

```bash
kubectl apply -k deploy/kubernetes
```

Default-deny and least-privilege intent is deliberate. Production operators must explicitly provide the correct egress, identity, database, provider, observability, storage and ingress configuration for the target environment.

## Provider routing

Core zWorkforce supports an OpenAI-compatible provider path and multi-provider routing. Example:

```env
ZWORKFORCE_PROVIDER=openai-compatible
ZWORKFORCE_PROVIDER_BASE_URL=https://api.openai.com/v1
ZWORKFORCE_PROVIDER_API_KEY_REF=env://OPENAI_API_KEY
ZWORKFORCE_MODEL_SOL=your-frontier-model
ZWORKFORCE_MODEL_TERRA=your-balanced-model
ZWORKFORCE_MODEL_LUNA=your-efficient-model
```

`ZWORKFORCE_PROVIDERS_JSON` configures provider pools/failover. Provider and storage secrets are resolved server-side and must not be emitted into browser assets.

For a standalone multi-provider compatibility gateway, see [`services/z-prov/`](services/z-prov/). For the consolidated platform gateway, see [`services/ai-gateway/`](services/ai-gateway/).

## Workflow, schedule and event automation

```bash
zworkforce workflow-upsert examples/workflow.research-report.json
zworkforce workflow-run research-report --input '{"topic":"AI workforce economics"}'
zworkforce workflow-tick

zworkforce schedule-upsert examples/schedule.daily-research.json
zworkforce event-rule-upsert examples/event-rule.incident.json
zworkforce event-emit incident.opened --dedupe-key incident-42 --payload '{"severity":"high"}'
zworkforce scheduler --once
```

Tenant policy documents are deterministic allow/deny rules. Explicit deny wins, and policies are enforced at submission/execution boundaries rather than being documentation-only metadata.

## Memory, artifacts and MCP

Local semantic memory is dependency-free; Qdrant can be used for a remote vector index. Artifacts can use local content-addressed storage or an S3-compatible backend.

Supported secret-reference schemes include:

```text
env://NAME
file:///run/secrets/provider#token
aws-sm://secret-id#token
vault://mount/path#token
```

The authenticated stateless MCP endpoint is `POST /mcp`. Representative tools include:

```text
workforce.submit_task
workforce.get_task
workforce.search_memory
workforce.run_workflow
workforce.emit_event
workforce.install_prometa
```

## Observability and AI FinOps

Core runtime surfaces include `/health`, `/ready`, `/metrics`, provider health/circuit metrics, queue/dead-letter metrics, model/provider cost metrics, workflow/outcome metrics and SLO gauges. Optional OTLP tracing and Prometheus/Grafana examples are under [`deploy/observability/`](deploy/observability/).

FinOps data can be attributed by tenant, department, agent, provider and model tier, supporting budgets, chargeback/showback, cost per successful outcome, rightsizing, capacity forecasting and SLO evaluation.

## Security boundaries

The repository intentionally keeps authority separated:

- Browser apps must not receive upstream provider keys or tenant-wide service tokens.
- Mutating agent jobs require the appropriate tenant/role/scope, declared mutation intent, policy and explicit approval/grants.
- Workspace shell/deploy requests execute only in the workspace runtime after explicit approval.
- HTTP/tool boundaries reject unsafe destinations and path traversal where applicable.
- `ZWallet` is a billing adapter, **not** a cryptocurrency signing/custody implementation.
- `Wall Street` is market intelligence, **not** an automated trading executor.
- `Zok` channel cards/simulators do not imply verified live commerce-channel delivery.
- `agent-control-panel` is currently a UI scaffold and must not be used as production secret storage.
- Z.A.R.V.I.S. private owner surfaces require their documented trusted-edge/loopback boundaries.
- Secrets, wallet keys, MPC material, card data, provider credentials and production identifiers must not be committed.

See [`SECURITY.md`](SECURITY.md) for the repository security policy.

## Release and evidence model

zWorkforce separates **repository readiness** from **environment readiness**:

1. Repository CI/tests/security checks validate the exact source tree.
2. Container/release workflows bind artifacts to immutable revisions/digests.
3. Staging/external suites collect environment evidence.
4. Production promotion requires an exact candidate plus explicit operator evidence and GO decision.
5. A passing repository workflow does **not** fabricate HA, DR, multi-region, storage, alert-delivery or trusted-signing evidence.

Key references:

- [`docs/PRODUCTION-EVIDENCE.md`](docs/PRODUCTION-EVIDENCE.md) — production evidence ledger and pending external gates.
- [`ROADMAP.md`](ROADMAP.md) and [`ROADMAPS.md`](ROADMAPS.md) — release/product roadmap authority.
- [`RUNBOOK.md`](RUNBOOK.md) — operational runbook.
- [`docs/GITHUB-OPERATIONS.md`](docs/GITHUB-OPERATIONS.md) — GitHub/release operations.
- [`docs/PROMETA-MASTER.md`](docs/PROMETA-MASTER.md) — master agents, skills and prompt metadata.
- [`docs/architecture/`](docs/architecture/) — consolidated architecture/ownership records.
- [`docs/operations/`](docs/operations/) — operational procedures and readiness runbooks.
- [`docs/release/`](docs/release/) — release records/templates/process.

## CLI surface

Representative core commands:

```text
serve | worker | scheduler | doctor | init
tenant-create | key-create | audit-verify
skill-sign | skill-install | prometa-install
workflow-upsert | workflow-run | workflow-tick
schedule-upsert | event-rule-upsert | event-emit
eval-upsert | eval-run | eval-tick
rag-reindex | rag-search | artifact-put
slo-set | slo-status | chargeback | capacity
outbox | mcp-tools | mcp-call
```

## Contributing

Read [`AGENTS.md`](AGENTS.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md) before making cross-boundary changes. Keep changes minimal, preserve tenant/security boundaries, update architecture/release documentation when behavior changes, and attach evidence to the exact commit under review.

## License

[MIT](LICENSE). Copyright (c) 2026 cvsz.
