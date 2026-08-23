# zWorkforce

**Enterprise AI Workforce Operating System — distributed control plane, durable agents, workflow automation, governance, MCP integration and AI FinOps.**

zWorkforce turns one or more LLM endpoints into a governed AI workforce. A tenant dispatches work to named agents; a cost-aware Luna/Terra/Sol router chooses a model tier; durable workers claim tasks; approvals and policy-as-code gate risky actions; workflows/schedules/events compose tasks; evaluation suites compare model strategies; memory and artifacts preserve knowledge; and the control plane measures cost, SLOs and business outcomes.

## v3.0.3 highlights

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

The repository also contains:
- The consolidated **Z.A.R.V.I.S.** product suite under [`packages/zarvis/`](packages/zarvis/), including its realtime voice client, speech provider registry, runtime skill catalog, API, operator surfaces, Windows client, and package-level CI.
- The **Zeto** AI Content Factory & M11/M12 Neural Operator Stack under [`packages/zeto/`](packages/zeto/), including ProMeta prompt compilers, multi-platform publishing adapters, QA scorecards, point-cloud canvas HUD, and M12 tool registry.
- The **ZSP AI Studio** & HyperFrames Video Generator under [`packages/zsp-aitool/`](packages/zsp-aitool/), an enterprise Thai-first affiliate marketing suite with 23 Prisma models, multi-scene video rendering, and vision OCR.
- The **Zider** AI Browser Companion under [`packages/zider/`](packages/zider/), a Manifest V3 Shadow DOM isolated sidebar, ChatPDF document intelligence, and multi-model group streaming gateway.
- The **Master Orchestrator & CLI** in [`control.sh`](control.sh) and [`cmd/zctl/`](cmd/zctl/) for single-command lifecycle management, diagnostics, and full validation.


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
git clone https://github.com/cvsz/zWorkforce.git
cd zWorkforce
cp .env.example .env
python3 -m pip install .
python3 -m zworkforce doctor
python3 -m zworkforce serve
```

> Commands use `python3`; fall back to `python` on systems where `python3` is unavailable (e.g. some Windows setups).

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
export ZWORKFORCE_POSTGRES_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export ZWORKFORCE_API_KEYS="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))'):superadmin:default:bootstrap:*"
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
ZWORKFORCE_S3_BUCKET=zworkforce
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

v3.0.3 provides real distributed execution through PostgreSQL, multiple API/worker replicas, leader-elected scheduler/outbox services, Kubernetes autoscaling, native OIDC, MCP, S3/Qdrant adapters and observability hooks. External services still need to exist and be operated: PostgreSQL HA, IdP, S3/Qdrant, OTLP collector, model providers and ingress/egress infrastructure. Multi-region database replication and disaster-recovery topology are infrastructure responsibilities rather than simulated inside the Python process. Release readiness for those external boundaries is recorded as real operator evidence in [docs/PRODUCTION-EVIDENCE.md](docs/PRODUCTION-EVIDENCE.md); repository CI does not claim those services are provisioned or exercised.

## License

[MIT](LICENSE). Copyright (c) 2026 cvsz.
