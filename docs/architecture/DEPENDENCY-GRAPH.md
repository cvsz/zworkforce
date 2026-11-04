# ZWorkforce Dependency Graph

**Generated:** 2026-11-05 UTC+7  
**Analysis Scope:** Python (687 files), Node.js/TypeScript (762 files), Infrastructure (Terraform, Kubernetes, Compose)

> [!NOTE] Machine-readable details are in [`DEPENDENCY-REPORT.json`](./DEPENDENCY-REPORT.json).

## Python Control Plane Dependencies

```mermaid
flowchart TD
    subgraph Control["zworkforce/ — Core Python Control Plane"]
        API["API Layer\n(FastAPI)"]
        Scheduler["Scheduler / Cron"]
        Worker["Worker / Queue Consumer"]
        Outbox["Webhook Outbox"]
        Repo["Repository Layer\n(SQLite + PostgreSQL)"]
        Auth["Auth / RBAC"]
        MCP["MCP Server\n(2026-07-28)"]
    end

    subgraph Packages["packages/ — Python Packages"]
        ZTI["ztrader_intel\n(FastAPI service)"]
        ZIDER["zider/server\n(FastAPI + Playwright)"]
    end

    subgraph External["External Python Dependencies"]
        FastAPI["fastapi"]
        Pydantic["pydantic"]
        HTTPX["httpx"]
        Psycopg["psycopg (PostgreSQL)"]
        SQLite["sqlite3 (stdlib)"]
        Prometheus["prometheus-fastapi-instrumentator"]
        OTel["opentelemetry-sdk"]
    end

    API --> FastAPI
    API --> Pydantic
    API --> Auth
    API --> Repo
    Repo --> SQLite
    Repo --> Psycopg
    Worker --> Repo
    Outbox --> Repo
    Scheduler --> Repo
    MCP --> API
    ZTI --> FastAPI
    ZTI --> Pydantic
    ZTI --> HTTPX
    ZTI --> SQLite
    ZTI --> Prometheus
    ZIDER --> FastAPI
    ZIDER --> Pydantic
    API --> OTel
```

## Node.js / MJS Service Dependencies

```mermaid
flowchart LR
    subgraph Services["services/ — Node.js MJS Microservices"]
        AIGateway["ai-gateway\n(express)"]
        Billing["billing-ledger\n(postgres-store.mjs)"]
        WorkspaceRT["workspace-runtime\n(express)"]
    end

    subgraph ZarvisServices["packages/zarvis/services/"]
        ZTaskGW["zarvis-task-gateway"]
        ZOrch["zarvis-orchestrator"]
        ZMemory["zarvis-memory"]
        ZPerception["zarvis-perception"]
        ZProactive["zarvis-proactive"]
        ZActionGW["zarvis-action-gateway"]
    end

    subgraph Apps["apps/ — Node.js Apps"]
        Zchat["zchat"]
        Zow["zow"]
        ZWallet["zwallet"]
        ZarvisConsole["zarvis-console"]
    end

    subgraph ExtNode["External Node.js Deps"]
        Express["express"]
        HPM["http-proxy-middleware"]
        PG["pg (PostgreSQL)"]
        Redis["ioredis"]
    end

    AIGateway --> Express
    AIGateway --> HPM
    AIGateway --> Redis
    Billing --> PG
    WorkspaceRT --> Express
    ZTaskGW --> Express
    ZTaskGW --> Redis
    Zow --> Express
    Zchat --> Express
```

## Cross-Service Communication

```mermaid
flowchart TD
    CF["Cloudflare Tunnel\n(zwf.zeaz.dev)"]
    Caddy["Caddy Reverse Proxy"]
    ZWF_API["zWorkforce Python API\n:8880"]
    AIGateway["ai-gateway\n:4000"]
    BillingLedger["billing-ledger\n:3001"]
    WorkspaceRT["workspace-runtime\n:7001"]
    ZarvisTaskGW["zarvis-task-gateway\n:3002"]

    CF --> Caddy
    Caddy --> ZWF_API
    Caddy --> AIGateway
    ZWF_API --> BillingLedger
    ZWF_API --> WorkspaceRT
    ZWF_API --> ZarvisTaskGW
    ZWF_API -->|"Supabase\nPooler :5432"| PostgreSQL[(PostgreSQL)]
```

## Top Third-Party Python Dependencies (by usage frequency)

| Package | References | Purpose |
|---|---|---|
| `fastapi` | 41 | HTTP API framework (control plane + service APIs) |
| `pytest` | 95 | Test framework |
| `httpx` | 39 | Async HTTP client (inter-service calls) |
| `pydantic` | — | Data validation (fastapi models) |
| `psycopg` | — | PostgreSQL async driver |
| `sqlite3` | — | stdlib SQLite (default store) |
| `prometheus_fastapi_instrumentator` | — | Prometheus metrics exposure |
| `opentelemetry` | — | Distributed tracing (OTLP/HTTP) |
| `hashlib` | 68 | SHA-256 artifact verification |
| `asyncio` | 41 | Async runtime |

## Circular Dependency Check

No circular imports detected between top-level packages in the Python control plane (`zworkforce/` is self-contained; `ztrader_intel` and `zider` are independent FastAPI services with no mutual imports).

> [!TIP] The `wire` module (74 references) is an internal `services/zc/src/wire/` package used by the ZCoder service. It has no cross-package circular dependencies.
