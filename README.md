# zWorkforce

![zWorkforce — Enterprise AI Workforce Operating System](docs/assets/zworkforce-social-preview.svg)

**Enterprise AI Workforce Operating System — distributed control plane, durable agents, workflow automation, governance, MCP integration and AI FinOps.**

zWorkforce turns one or more LLM endpoints into a governed AI workforce. A tenant dispatches work to named agents; a cost-aware Luna/Terra/Sol router chooses a model tier; durable workers claim tasks; approvals and policy-as-code gate risky actions; workflows/schedules/events compose tasks; evaluation suites compare model strategies; memory and artifacts preserve knowledge; and the control plane measures cost, SLOs and business outcomes.

## v3.0.4 highlights

- **Production image hardening** installs the S3 runtime extra and uses an in-image Python healthcheck for the HA deployment, so the published image's declared artifact backend and liveness contract agree.

- **PostgreSQL distributed runtime** with `FOR UPDATE SKIP LOCKED` task leasing for cross-host workers; SQLite/WAL remains the zero-config local backend.
- **Workflow DAG engine** with dependency validation, versioning, templated inputs/results and durable step state.
- **Cron + interval scheduler** and **durable event triggers** with dedupe keys, filters and agent/workflow targets.
- **Active/passive service leader leases** for scheduler and outbox processes so multiple replicas can be deployed safely.
- **A/B model evaluation suites** that run real tasks across tier variants and recommend the quality/cost winner.
- **Policy-as-code** with tenant-scoped allow/deny rules enforced at task submission and tool execution.
- **Native OIDC** JWT validation plus the existing signed identity-aware proxy boundary for SAML/brokered identity deployments.
- **Secret references** from environment, mounted files, AWS Secrets Manager and Vault KV v2.
- **MCP 2026-07-28 stateless endpoint/client** exposing task, workflow, event and memory management as MCP tools.
- **Content-addressed artifacts** with local or S3-compatible runtime-selectable storage.
- **Semantic memory** with local feature-hash vectors or Qdrant + OpenAI-compatible embedding endpoint.
- **OTLP/HTTP JSON tracing**, Prometheus metrics and a Grafana dashboard.
- **Chargeback/showback, capacity forecast and SLO evaluation**.
- **Agent templates and immutable semantic agent versions**.
- **Signed remote skill registry** over HTTPS.
- **Durable webhook outbox** with HMAC signatures, retry/backoff and leader election.
- **Kubernetes deployment** with hardened pods, API/worker scaling, PDBs, persistent artifacts/workspace and default-deny network policy.
- **Release-governance hardening** with a dedicated documentation/policy CI gate, desired-state default-branch ruleset contract, stronger release verifier, and explicit production evidence ledger.
- **Refreshed native WinUI operator shell and Overview dashboard** while preserving existing API and view-model contracts.

All v2 capabilities remain: multi-tenancy, RBAC/scopes, four-eyes approvals, provider failover/circuit breakers, bounded tools, tamper-evident audit chains, budgets, deterministic outcomes, rightsizing recommendations, dashboard, Docker and Python 3.12–3.14 support.

## Monorepo catalog

The repository is both the **zWorkforce governed AI control plane** and a broader product monorepo. The JavaScript workspace is defined by `apps/*`, `services/*`, and `packages/*`; the Python control-plane runtime remains under `zworkforce/`. Product boundaries are kept explicit so browser applications do not inherit provider, infrastructure, payment, or mutation authority from backend services.

### Apps (10)

| App | Responsibility |
| --- | --- |
| [`apps/agent-control-panel`](apps/agent-control-panel/) | Next.js agent-control operator surface and control-panel UI shell. |
| [`apps/frontend`](apps/frontend/) | Frontend UI/UX stack containing ReUI Dashboard, Canva App, MetricUI Analytics, and Canva Dev MCP integrations. |
| [`apps/zaicoder`](apps/zaicoder/) | Coding-agent application whose browser/CLI traffic is routed through the platform AI Gateway; upstream provider credentials stay server-side. |
| [`apps/zarvis-console`](apps/zarvis-console/) | Private owner-only Z.A.R.V.I.S. browser command center backed by the Z.A.R.V.I.S. orchestrator. |
| [`apps/zarvis-windows`](apps/zarvis-windows/) | Native Windows 11 Z.A.R.V.I.S. client using local SSH forwarding rather than exposing a public origin. |
| [`apps/zchat`](apps/zchat/) | Conversation UI with local conversation UX, model selection, safe Markdown, streaming, and server-side AI Gateway routing. |
| [`apps/zeaz-web`](apps/zeaz-web/) | Production `zeaz.dev` / ZEAZ One web application using Cloudflare Workers + D1, bilingual EN/TH pages, and early-access APIs. |
| [`apps/zow`](apps/zow/) | User-facing workspace layer; validation, shell, and deployment actions are delegated to the approval-gated workspace runtime. |
| [`apps/zvoice`](apps/zvoice/) | Realtime browser voice client with short-lived signed gateway tickets, AudioWorklet capture, and optional owner-only Z.A.R.V.I.S. mode. |
| [`apps/zwallet`](apps/zwallet/) | Audited billing adapter for invoice intents and credits. It intentionally has no wallet signing, card, KYC, MPC, swap, or private-key authority. |

### Services (18)

| Service | Responsibility / security boundary |
| --- | --- |
| [`services/agent-orchestrator`](services/agent-orchestrator/) | Approval-gated asynchronous agent-job lifecycle, scoped worker execution, retry/cancel, and audit correlation. |
| [`services/agent-provider`](services/agent-provider/) | Node service backing agent-provider/job-store flows used by platform jobs and backup integration paths. |
| [`services/ai-gateway`](services/ai-gateway/) | Authenticated Express/Redis model gateway with model catalog, provider routing, rate limiting, and structured secret redaction. |
| [`services/billing-ledger`](services/billing-ledger/) | Idempotent usage/billing ledger; explicitly excludes wallet keys, MPC shares, card data, and transaction signing. |
| [`services/phase6-api`](services/phase6-api/) | FastAPI staging-verification surface for AI providers, uploads, webhooks, Supabase, metrics, and agent-store integration. |
| [`services/voice-agent`](services/voice-agent/) | Realtime speech-to-speech worker with configurable STT, chat-completions LLM backend, VAD, and TTS pipeline. |
| [`services/voice-gateway`](services/voice-gateway/) | Voice edge/gateway issuing short-lived HMAC-signed tickets and enforcing service-side session boundaries. |
| [`services/workspace-runtime`](services/workspace-runtime/) | Isolated generated-project execution boundary; shell/deploy require explicit approved grants. |
| [`services/z-prov`](services/z-prov/) | ZeaZ multi-provider AI gateway exposing Anthropic Messages and OpenAI-compatible Chat Completions / Responses surfaces under stable `zeaz-*` aliases. |
| [`services/zarvis-action-gateway`](services/zarvis-action-gateway/) | Owner-only reversible mutation gateway with dry-run preview, digest/nonce approval, compare-and-set execution, rollback, and emergency stop. |
| [`services/zarvis-memory`](services/zarvis-memory/) | AES-256-GCM owner-confirmed memory service with proposal/confirmation flow and secret-sensitive-content rejection. |
| [`services/zarvis-orchestrator`](services/zarvis-orchestrator/) | Converts owner text/voice into constrained tool calls, speech-ready results, immutable audit events, and durable session state. |
| [`services/zarvis-owner-voice-edge`](services/zarvis-owner-voice-edge/) | Local owner voice proxy that injects the fixed owner assertion and edge secret server-side before forwarding to ZVoice. |
| [`services/zarvis-perception`](services/zarvis-perception/) | Consent-based one-shot image/document/screen/camera analysis; no continuous hidden capture, biometric identification, or raw-media persistence. |
| [`services/zarvis-proactive`](services/zarvis-proactive/) | Bounded read-only proactive scheduler with quiet hours, budgets, confidence/cooldown controls, explainable suggestions, and no autonomous mutation. |
| [`services/zarvis-task-gateway`](services/zarvis-task-gateway/) | Durable owner-only multi-step task surface with exact-plan digest/nonce approval, pause/resume, and constrained worker execution. |
| [`services/zc-api`](services/zc-api/) | Consolidated Phase-6/staging verification API with Kubernetes liveness/readiness and Prometheus integration. |
| [`services/zc`](services/zc/) | Full-stack interactive AI coding agent surface: supported API server plus compatibility CLI/terminal and webapp components. |

### Packages (11)

| Package | Type | Responsibility |
| --- | --- | --- |
| [`packages/contracts`](packages/contracts/) | in-tree | Shared versioned request, event, error, AI, agent, and Z.A.R.V.I.S. contracts. |
| [`packages/wall-street`](packages/wall-street/) | in-tree | Market-intelligence operator surface using public TradingView embed and public market feeds; does not submit exchange orders or collect exchange keys. |
| [`packages/zarvis`](packages/zarvis/) | in-tree | Consolidated Z.A.R.V.I.S. product suite: console, Windows/voice surfaces, orchestration, memory, perception, proactive runtime, contracts, deployment, and operations. |
| [`packages/zeto`](packages/zeto/) | in-tree | AI Content Factory and publishing automation stack spanning ideation, generation, approval, scheduling, publishing, monitoring, and learning. |
| [`packages/zider`](packages/zider/) | in-tree | Enterprise browser AI companion: MV3 sidebar, multi-model chat, ChatPDF, web/YouTube intelligence, translation, artifacts, voice, OCR, and creative tools. |
| [`packages/zsp-aitool`](packages/zsp-aitool/) | in-tree | Thai-first Shopee Affiliate SaaS / ZSP AI Studio with product ingestion, AI content, OCR, affiliate workflows, and HyperFrames video rendering. |
| [`packages/ztrader/zeaz-intelligence`](packages/ztrader/zeaz-intelligence/) | in-tree | zTrader decision-support sidecar for narrative, whale, rug-risk, opportunity/risk/confidence scoring, DexScreener, optional GoPlus, and optional supplied-evidence Grok/xAI summaries. It does not blindly auto-execute trades. |
| [`packages/zksato`](packages/zksato) | Git submodule | Risk-first SET/TFEX research and paper-execution control plane; live-money mutation remains explicitly gated. |
| [`packages/zmovie`](packages/zmovie) | Git submodule | Self-hosted AI movie production pipeline with continuity-aware storyboards, durable rendering, assembly, and approval-gated publishing. |
| [`packages/zok`](packages/zok) | Git submodule | Conversational-commerce workspace currently operated as a hardened developer/sandbox release with simulated channel delivery boundaries. |
| [`packages/zttshop-php`](packages/zttshop-php) | Git submodule | PHP 8.1+ client SDK for TikTok Shop Open Platform resources including auth, products, orders, logistics, finance, returns, warehouse, and video. |

The four Git-linked package entries are pinned in [`.gitmodules`](.gitmodules). Clone them with the repository or initialize them afterward:

```bash
git clone --recurse-submodules https://github.com/cvsz/zworkforce.git
# or, from an existing clone:
git submodule update --init --recursive
```

### Other top-level platform surfaces

| Path | Purpose |
| --- | --- |
| [`zworkforce/`](zworkforce/) | Core Python control plane: API/CLI, durable tasks, workflows, scheduler, policy, providers, MCP, RAG, artifacts, workspaces, FinOps, telemetry, and safety hooks. |
| [`ZWorkforceClient/`](ZWorkforceClient/) | Native Windows operator client for the zWorkforce REST control plane. |
| [`cmd/zctl/`](cmd/zctl/) + [`control.sh`](control.sh) | Master lifecycle/diagnostic/validation command surfaces for the monorepo. |
| [`infrastructure/`](infrastructure/) | Kubernetes/Kustomize, Argo CD, Cilium, and Terraform/Cloudflare infrastructure definitions. |
| [`deploy/`](deploy/) | Caddy, Cloudflare Tunnel, HA Compose, Kubernetes, observability, and systemd deployment assets. |
| [`.agents/skills/`](.agents/skills/) | Repo-local agent skills covering review, release verification, Kubernetes, observability, DR, policy, MCP, FinOps, RAG, GitHub operations, and related operator workflows. |
| [`automation/`](automation/) + [`plugins/`](plugins/) | Automation and extension/plugin integration surfaces. |
| [`schemas/`](schemas/) + [`prompts/`](prompts/) | Versioned schemas and prompt assets shared across agent workflows. |
| [`examples/`](examples/) | Runnable examples and ProMeta seed catalogs. |
| [`tests/`](tests/) | Root integration, governance, security, release, dependency, and control-plane test coverage. |

## Architecture

```text
Users / OIDC / Signed Proxy / MCP Clients
                    |
                    v
+--------------------------------------------------+
| zWorkforce Control Plane                        |
| tenants / RBAC / policy / agents / approvals    |
| workflows / schedules / events / evaluations    |
| memory / artifacts / audit / FinOps / SLOs      |
+-------------------------+------------------------+
                          |
                          v
              +-----------------------+
              | Durable State / Queue |
              | SQLite or PostgreSQL  |
              +-----------+-----------+
                          |
        +-----------------+------------------+
        |                 |                  |
        v                 v                  v
   Worker Pool       Scheduler HA        Outbox HA
        |                 |                  |
        +-----------------+------------------+
                          |
                          v
                 +------------------+
                 | Model Router     |
                 | Luna/Terra/Sol   |
                 +--------+---------+
                          |
              +-----------+-----------+
              |                       |
              v                       v
       Provider Pool             Tool Gateway
    health / fallback        workspace / HTTP / shell
                             memory / sub-agents
              |
              v
   OTLP / Prometheus / Grafana / Artifacts / Qdrant / S3
```

See [ARCHITECTURE.md](ARCHITECTURE.md), [SECURITY.md](SECURITY.md),
[docs/THREAT-MODEL.md](docs/THREAT-MODEL.md), and
[docs/GITHUB-OPERATIONS.md](docs/GITHUB-OPERATIONS.md). The master agent,
skill and prompt-metadata operating model is documented in
[docs/PROMETA-MASTER.md](docs/PROMETA-MASTER.md). Production release evidence
is recorded in [docs/PRODUCTION-EVIDENCE.md](docs/PRODUCTION-EVIDENCE.md).
Installable repo-local Codex skills live under [`.agents/skills/`](.agents/skills/) and runtime-ready
ProMeta seed catalogs are provided in
[`examples/prometa-agent-catalog.json`](examples/prometa-agent-catalog.json)
[`examples/prometa-skills.json`](examples/prometa-skills.json),
[`examples/prometa-agent-templates.json`](examples/prometa-agent-templates.json)
and [`examples/prometa-workflows.json`](examples/prometa-workflows.json).
Install the full ProMeta runtime baseline with `zworkforce prometa-install`.

## Quick start — local SQLite

```bash
git clone --recurse-submodules https://github.com/cvsz/zworkforce.git
cd zworkforce
cp .env.example .env
python -m pip install .
python -m zworkforce doctor
python -m zworkforce serve
```

Open `http://localhost:9569`. Development bootstrap credentials are not for production.

### Windows 11 client

The native Windows 11 operator client is under [`ZWorkforceClient/`](ZWorkforceClient/).
It connects to the existing REST control plane; setup, packaged build, secure
credential storage, and GitHub Windows CI are documented in
[`docs/WINDOWS-CLIENT.md`](docs/WINDOWS-CLIENT.md).

### Create a persistent API key

```bash
zworkforce key-create --name automation --role operator --scopes workforce:read
```

The one-time secret is stored in a new mode-0600 file under `$ZWORKFORCE_DATA_DIR/api-keys/`;
the CLI prints metadata and the file path, never the secret. Use `--secret-file PATH` for an
explicit destination. Existing secret files are not overwritten.

## Production Compose — PostgreSQL

```bash
export ZWORKFORCE_POSTGRES_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export ZWORKFORCE_API_KEYS="$(python -c 'import secrets; print(secrets.token_urlsafe(32))'):superadmin:default:bootstrap:*"
docker compose up -d --build
```

Compose runs PostgreSQL, API, worker and scheduler. Start the optional durable integration dispatcher with:

```bash
docker compose --profile integrations up -d outbox
```

## Kubernetes

```bash
kubectl apply -k deploy/kubernetes
```

The supplied manifests intentionally use default-deny network egress. Add environment-specific egress for PostgreSQL, model providers, OIDC/JWKS, OTLP, approved HTTP tools and object/vector stores before production traffic.

## Storage backends

### SQLite

Default for development and single-host use.

### PostgreSQL

```env
ZWORKFORCE_DATABASE_URL=postgresql://user:password@db.example.com:5432/zworkforce
```

The same worker runtime uses transactional `SKIP LOCKED` claims, leases, heartbeats, retries and dead-letter state across hosts.

## Providers

Single OpenAI-compatible endpoint:

```env
ZWORKFORCE_PROVIDER=openai-compatible
ZWORKFORCE_PROVIDER_BASE_URL=https://api.openai.com/v1
ZWORKFORCE_PROVIDER_API_KEY_REF=env://OPENAI_API_KEY
ZWORKFORCE_MODEL_SOL=your-frontier-model
ZWORKFORCE_MODEL_TERRA=your-balanced-model
ZWORKFORCE_MODEL_LUNA=your-efficient-model
```

Multi-provider failover uses `ZWORKFORCE_PROVIDERS_JSON`. Each provider can use `api_key_ref` so secrets are resolved server-side before provider initialization.

## Workflow example

```json
{
  "id": "research-report",
  "name": "Research report",
  "definition": {
    "steps": [
      {"id": "research", "agent_id": "researcher", "prompt": "Research {{input.topic}}"},
      {"id": "review", "agent_id": "management", "depends_on": ["research"], "prompt": "Review and summarize: {{steps.research.result}}"}
    ]
  }
}
```

```bash
zworkforce workflow-upsert examples/workflow.research-report.json
zworkforce workflow-run research-report --input '{"topic":"AI workforce economics"}'
zworkforce workflow-tick
```

## Schedules and events

Schedules support 5-field cron and interval triggers. Events are durable and can be deduplicated by `source + dedupe_key`.

```bash
zworkforce schedule-upsert examples/schedule.daily-research.json
zworkforce event-rule-upsert examples/event-rule.incident.json
zworkforce event-emit incident.opened --dedupe-key incident-42 --payload '{"severity":"high","title":"API unavailable"}'
zworkforce scheduler --once
```

## Policy as code

Tenant policies are deterministic JSON allow/deny rules. Explicit deny wins. Example:

```json
{
  "id": "production-guard",
  "document": {
    "default": "allow",
    "rules": [
      {"id": "no-finance-shell", "effect": "deny", "action": "tool.shell_exec", "when": {"department": "finance"}},
      {"id": "no-mutating-sales", "effect": "deny", "action": "task.submit", "when": {"department": "sales", "mutating": true}}
    ]
  }
}
```

Policies are enforced by the production `PolicyEngine`, not only stored for documentation.

## Evaluation / model optimization

Evaluation suites execute each test case across 2–8 tier variants using real task execution and outcome criteria.

```bash
zworkforce eval-upsert examples/evaluation.tiers.json
zworkforce eval-run tiers
zworkforce eval-tick
```

The summary ranks pass rate and outcome score first, then cost and duration, and reports a recommended variant.

## Memory / RAG

Local semantic memory is dependency-free:

```env
ZWORKFORCE_VECTOR_BACKEND=local
```

For a scalable remote index:

```env
ZWORKFORCE_VECTOR_BACKEND=qdrant
ZWORKFORCE_QDRANT_URL=https://qdrant.example.com
ZWORKFORCE_QDRANT_COLLECTION=zworkforce-memory
ZWORKFORCE_EMBEDDING_BASE_URL=https://api.openai.com/v1
ZWORKFORCE_EMBEDDING_API_KEY=...
ZWORKFORCE_EMBEDDING_MODEL=text-embedding-3-small
```

## Artifacts

Local content-addressed store:

```env
ZWORKFORCE_ARTIFACT_BACKEND=local
ZWORKFORCE_ARTIFACT_DIR=/artifacts
```

S3-compatible:

```env
ZWORKFORCE_ARTIFACT_BACKEND=s3
ZWORKFORCE_S3_BUCKET=zworkforce-artifacts
ZWORKFORCE_S3_PREFIX=zworkforce
```

Every artifact records SHA-256, size, content type, tenant, actor and optional task/workflow association.

## Identity

Native OIDC validates issuer, audience, signature, timestamps and asymmetric algorithms through provider discovery/JWKS. Tenant/role/scope/name claim names are configurable. Group-to-role mapping is supported.

For SAML deployments, terminate SAML at a hardened identity-aware proxy/broker and use zWorkforce's signed HMAC proxy identity boundary. zWorkforce deliberately does not implement a custom SAML parser.

## Secret stores

Supported reference schemes:

```text
env://NAME
file:///run/secrets/provider#token
aws-sm://secret-id#token
vault://mount/path#token
```

References are supported for database DSNs, provider keys, skill signing keys, proxy identity secrets and outbox signing secrets.

## MCP

`POST /mcp` is an authenticated stateless MCP endpoint. Management tools include:

```text
workforce.submit_task
workforce.get_task
workforce.search_memory
workforce.run_workflow
workforce.emit_event
workforce.install_prometa
```

CLI:

```bash
zworkforce mcp-tools https://workforce.example.com/mcp
zworkforce mcp-call https://workforce.example.com/mcp workforce.get_task --arguments '{"task_id":"..."}'
```

## Observability

- `/health`
- `/ready`
- `/metrics`
- provider health/circuit metrics
- queue/dead-letter metrics
- model/provider cost metrics
- outcome and workflow metrics
- SLO gauges
- optional OTLP/HTTP JSON traces
- Prometheus + Grafana examples under `deploy/observability/`

## AI FinOps / economics

zWorkforce tracks token/credit spend by tenant, department, agent, provider and model tier. It exposes budgets, chargeback/showback, cost per successful outcome, rightsizing recommendations, capacity forecasts and SLO compliance.

## CLI surface

```text
serve | worker | scheduler | doctor | init
tenant-create | key-create | audit-verify
skill-sign | skill-install
prometa-install
workflow-upsert | workflow-run | workflow-tick
schedule-upsert | event-rule-upsert | event-emit
eval-upsert | eval-run | eval-tick
rag-reindex | rag-search | artifact-put
slo-set | slo-status | chargeback | capacity
outbox | mcp-tools | mcp-call
```

## Security model

Provider and storage secrets stay server-side. Mutating work is gated by RBAC/scopes, tenant context, agent grants, declared mutation intent, approval rules, policy-as-code and server-side capability flags. Shell is `shell=False` with an executable allowlist and sanitized environment. HTTP tools are allowlisted, revalidate redirects and reject private/non-routable destinations by default. Audit events are hash chained per tenant.

See [SECURITY.md](SECURITY.md).

## Deployment boundary

v3.0.4 provides real distributed execution through PostgreSQL, multiple API/worker replicas, leader-elected scheduler/outbox services, Kubernetes autoscaling, native OIDC, MCP, S3/Qdrant adapters and observability hooks. It carries the v3.0.3 execution surface with the production-image fixes described above. External services still need to exist and be operated: PostgreSQL HA, IdP, S3/Qdrant, OTLP collector, model providers and ingress/egress infrastructure. Multi-region database replication and disaster-recovery topology are infrastructure responsibilities rather than simulated inside the Python process. Release readiness for those external boundaries is recorded as real operator evidence in [docs/PRODUCTION-EVIDENCE.md](docs/PRODUCTION-EVIDENCE.md); repository CI does not claim those services are provisioned or exercised.

## License

[MIT](LICENSE). Copyright (c) 2026 cvsz.
