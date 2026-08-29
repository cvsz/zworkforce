# Configuration Architecture

## Environment variable inventory

### Core platform

| Variable | Purpose | Used By | Required | Type | Default | Notes |
|---|---|---|---|---|---|---|
| `Z_PLATFORM_SERVICE_TOKEN` | Internal bearer token for service-to-service auth | All services, zc, apps | Yes | string (>=32 bytes) | — | Must be generated with `openssl rand -hex 32` |
| `Z_PLATFORM_RELEASE_SHA` | Release commit SHA for health endpoints | ai-gateway, zchat | No | string (40 hex chars) | `unknown` | |
| `HOST` | Bind address | All Node services | No | string | `127.0.0.1` | |
| `PORT` | Bind port | All Node services | No | integer | service-specific | |
| `LOG_LEVEL` | Logging verbosity | ai-gateway, zc | No | string | `info` | |
| `NODE_ENV` | Runtime environment | Docker | No | string | `production` | |

### AI Gateway

| Variable | Purpose | Used By | Required | Type | Default | Notes |
|---|---|---|---|---|---|---|
| `AI_GATEWAY_CORS_ORIGIN` | CORS origin (comma-separated) | ai-gateway | No | string | — | Wildcard denied |
| `AI_GATEWAY_RATE_LIMIT_WINDOW_MS` | Rate limit window | ai-gateway | No | integer | `60000` | |
| `AI_GATEWAY_RATE_LIMIT_MAX` | Rate limit max requests | ai-gateway | No | integer | `60` | |
| `AI_GATEWAY_JSON_LIMIT` | JSON body limit | ai-gateway | No | string | `32mb` | |
| `REDIS_URL` | Redis connection | ai-gateway, phase6-api, zc | Yes | URL | `redis://localhost:6379` | |
| `UPSTREAM_BASE_URL` | Single upstream provider | ai-gateway | No | URL | — | |
| `UPSTREAM_PROVIDER` | Single provider adapter name | ai-gateway | No | string | `openai-compatible` | |
| `UPSTREAM_PROVIDERS_JSON` | Multi-provider chain | ai-gateway | No | JSON array | — | Precedence over single-provider vars |
| `AI_PROVIDER_KEYS_JSON` | Server-side provider key pool | ai-gateway | No | JSON object | `{}` | Seeded into Redis at startup |
| `AI_MODELS_JSON` | Model catalog override | ai-gateway | No | JSON array | `[]` | |
| `AI_MODEL` | Fallback model ID | ai-gateway, zchat, zaicoder | No | string | `default` | |
| `ANTHROPIC_UPSTREAM_BASE_URL` | Anthropic upstream | ai-gateway | No | URL | `https://api.anthropic.com/v1` | |
| `ANTHROPIC_VERSION` | Anthropic API version | ai-gateway | No | string | `2023-06-01` | |
| `ANTHROPIC_BETA` | Anthropic beta header | ai-gateway | No | string | — | |
| `GITHUB_WEBHOOK_SECRET` | GitHub webhook HMAC secret | phase6-api | No | string | — | |
| `AI_GATEWAY_PROVIDER_TOKEN` | Provider token (deprecated?) | — | No | string | — | |
| `UPSTREAM_API_KEY` | Upstream API key (deprecated?) | — | No | string | — | |

### Provider credentials (grouped)

Each provider follows the pattern `<PROVIDER>_API_KEY` and `<PROVIDER>_BASE_URL`. See `.env.example` for full list.

**Known providers:** NVIDIA_NIM, GROQ, CEREBRAS, SAMBANOVA, OPENROUTER, GITHUB_MODELS, MISTRAL, CODESTRAL, SCALEWAY, GEMINI, ZAI, DASHSCOPE, CLOUDFLARE, OVHCLOUD, OPENCODE, DEEPSEEK, KIMI, WAFER, FIREWORKS, OLLAMA, LLAMACPP, LM_STUDIO.

### Agent Orchestrator

| Variable | Purpose | Used By | Required | Type | Default | Notes |
|---|---|---|---|---|---|---|
| `AGENT_ORCHESTRATOR_PROVIDER_MODE` | memory vs production adapters | agent-orchestrator | No | string | `memory` | |
| `AGENT_JOB_STORE_URL` | Job store backend | agent-orchestrator | Conditional | URL | — | Required in production |
| `AGENT_QUEUE_URL` | Queue backend | agent-orchestrator | Conditional | URL | — | Required in production |
| `AGENT_AUDIT_URL` | Audit sink backend | agent-orchestrator | Conditional | URL | — | Required in production |
| `AGENT_IDENTITY_URL` | Identity provider backend | agent-orchestrator | Conditional | URL | — | Required in production |
| `AGENT_SANDBOX_URL` | Sandbox runtime backend | agent-orchestrator | Conditional | URL | — | Required in production |
| `AGENT_PROVIDER_TIMEOUT_MS` | HTTP client timeout | agent-orchestrator | No | integer | `5000` | |
| `AGENT_SANDBOX_TIMEOUT_MS` | Sandbox execution timeout | agent-orchestrator | No | integer | `30000` | |
| `AGENT_EXTERNAL_TRAFFIC_ENABLED` | Allow external traffic | agent-orchestrator | No | boolean | `false` | |

### Agent Provider

| Variable | Purpose | Used By | Required | Type | Default | Notes |
|---|---|---|---|---|---|---|
| `DATA_DIR` | Persistent data directory | agent-provider | No | path | `/data` | |
| `AGENT_TEST_FAILURE_INJECTION` | Readiness failure injection | agent-provider | No | boolean | `false` | |

### Billing Ledger

| Variable | Purpose | Used By | Required | Type | Default | Notes |
|---|---|---|---|---|---|---|
| `Z_PLATFORM_BILLING_LEDGER_URL` | Billing ledger URL | zwallet | No | URL | — | |

### Workspace Runtime

| Variable | Purpose | Used By | Required | Type | Default | Notes |
|---|---|---|---|---|---|---|
| `Z_PLATFORM_WORKSPACE_RUNTIME_URL` | Workspace runtime URL | zow | No | URL | — | |

### Voice

| Variable | Purpose | Used By | Required | Type | Default | Notes |
|---|---|---|---|---|---|---|
| `Z_PLATFORM_VOICE_GATEWAY_URL` | Voice gateway URL | zvoice | No | URL | — | |
| `VOICE_TICKET_SECRET` | Voice ticket HMAC secret | voice-gateway | Yes | string (>=32 bytes) | — | |
| `VOICE_TICKET_TTL_SECONDS` | Ticket TTL | voice-gateway | No | integer | `60` | |
| `VOICE_MAX_SESSIONS` | Max concurrent sessions | voice-gateway | No | integer | `4` | |
| `VOICE_MAX_SESSIONS_PER_IP` | Max sessions per IP | voice-gateway | No | integer | `2` | |
| `VOICE_AGENT_URL` | Voice agent upstream | voice-gateway | No | URL | `http://voice-agent:8765` | |
| `VOICE_PUBLIC_WS_URL` | Public WebSocket URL | voice-gateway | No | URL | `ws://127.0.0.1:8450/v1/realtime` | |
| `VOICE_ALLOW_ANONYMOUS` | Allow anonymous voice | voice-gateway, zvoice | No | boolean | `false` | |
| `VOICE_LLM_MODEL` | Voice LLM model | zvoice | No | string | `default` | |
| `ZARVIS_LOCAL_LLM_BASE_URL` | Local LLM endpoint | zvoice | No | URL | — | |
| `ZARVIS_LOCAL_LLM_MODEL` | Local LLM model | zvoice | No | string | `qwen3:8b` | |
| `ZARVIS_LOCAL_LLM_API_KEY` | Local LLM API key | zvoice | No | string | — | |
| `ZARVIS_LOCAL_LLM_TIMEOUT_MS` | Local LLM timeout | zvoice | No | integer | `45000` | |
| `ZVOICE_ZARVIS_MODE` | Enable Zarvis bridge | zvoice | No | boolean | `false` | |
| `ZVOICE_ALLOW_ANONYMOUS` | Allow anonymous access | zvoice | No | boolean | `false` | |

### ZARVIS local

| Variable | Purpose | Used By | Required | Type | Default | Notes |
|---|---|---|---|---|---|---|
| `ZARVIS_EDGE_SHARED_SECRET` | Edge secret for owner access | zarvis-*, zvoice, zarvis-console | Yes | string (>=32 bytes) | — | |
| `ZARVIS_ORCHESTRATOR_URL` | Orchestrator URL | zvoice, zarvis-console | Conditional | URL | — | |
| `ZARVIS_ORCHESTRATOR_SERVICE_TOKEN` | Orchestrator service token | zarvis-console | Yes | string (>=32 bytes) | — | |
| `ZARVIS_OWNER_GITHUB_ID` | Owner GitHub ID | zarvis-* | Yes | string | `4076926` | |
| `ZARVIS_LOCAL_OWNER_TOKEN` | Owner token for proactive | zarvis-proactive | Yes | string (>=32 bytes) | — | |
| `ZARVIS_PROACTIVE_WORKER_TOKEN` | Worker token for proactive | zarvis-proactive | Yes | string (>=32 bytes) | — | |
| `ZARVIS_ACTION_WORKER_TOKEN` | Worker token for action gateway | zarvis-task-gateway | Yes | string (>=32 bytes) | — | |
| `ZARVIS_TASK_WORKER_TOKEN` | Worker token for task gateway | zarvis-task-gateway | Yes | string (>=32 bytes) | — | |
| `ZARVIS_MEMORY_WORKER_TOKEN` | Worker token for memory | zarvis-memory | Yes | string (>=32 bytes) | — | |
| `ZARVIS_MEMORY_MASTER_KEY_B64` | Memory encryption master key | zarvis-memory | Yes | base64 string | — | |
| `ZARVIS_PERCEPTION_WORKER_TOKEN` | Worker token for perception | zarvis-perception | Yes | string (>=32 bytes) | — | |
| `ZARVIS_PERCEPTION_MASTER_KEY_B64` | Perception encryption master key | zarvis-perception | Yes | base64 string | — | |
| `ZARVIS_DATA_DIR` | Zarvis data root | zarvis-orchestrator | No | path | `./data/zarvis` | |
| `ZARVIS_ACTION_HOST` | Action gateway bind | zarvis-action-gateway | No | string | `127.0.0.1` | Loopback only |
| `ZARVIS_ACTION_PORT` | Action gateway port | zarvis-action-gateway | No | integer | `8098` | |
| `ZARVIS_ACTION_HEALTH_URL` | Action health URL | zarvis-proactive | No | URL | `http://127.0.0.1:8098/healthz` | |
| `ZARVIS_PROACTIVE_HOST` | Proactive bind | zarvis-proactive | No | string | `127.0.0.1` | Loopback only |
| `ZARVIS_PROACTIVE_PORT` | Proactive port | zarvis-proactive | No | integer | `8099` | |

### Loopback host ports (Compose)

| Variable | Purpose | Default |
|---|---|---|
| `AI_GATEWAY_PORT` | AI Gateway loopback port | `8400` |
| `AGENT_ORCHESTRATOR_PORT` | Agent Orchestrator loopback port | `8500` |
| `AGENT_PROVIDER_PORT` | Agent Provider loopback port | `8800` |
| `WORKSPACE_RUNTIME_PORT` | Workspace Runtime loopback port | `8600` |
| `BILLING_LEDGER_PORT` | Billing Ledger loopback port | `8700` |
| `ZCHAT_PORT` | ZChat loopback port | `3021` |
| `ZWALLET_PORT` | ZWallet loopback port | `3040` |
| `ZCHAT_SESSION_TTL_SECONDS` | ZChat session TTL | `3600` |

### Staging smoke overrides

| Variable | Purpose | Default |
|---|---|---|
| `STAGING_SMOKE_ZCHAT_URL` | ZChat smoke target | `http://127.0.0.1:3021` |
| `STAGING_SMOKE_ZWALLET_URL` | ZWallet smoke target | `http://127.0.0.1:3040` |
| `STAGING_SMOKE_AI_GATEWAY_URL` | AI Gateway smoke target | `http://127.0.0.1:8400` |
| `STAGING_SMOKE_AGENT_ORCHESTRATOR_URL` | Agent Orchestrator smoke target | `http://127.0.0.1:8500` |
| `STAGING_SMOKE_WORKSPACE_RUNTIME_URL` | Workspace Runtime smoke target | `http://127.0.0.1:8600` |
| `STAGING_SMOKE_BILLING_LEDGER_URL` | Billing Ledger smoke target | `http://127.0.0.1:8700` |
| `STAGING_SMOKE_AGENT_PROVIDER_URL` | Agent Provider smoke target | `http://127.0.0.1:8800` |

## Duplicate / obsolete variables

| Variable | Issue | Recommendation |
|---|---|---|
| `AI_GATEWAY_PROVIDER_TOKEN` | Not used in current ai-gateway code; auth uses `Z_PLATFORM_SERVICE_TOKEN` | Remove from `.env.example` |
| `UPSTREAM_API_KEY` | Not used in current ai-gateway code | Remove from `.env.example` |
| `PROVIDER_TOKEN` | Not used in current ai-gateway code | Remove from `.env.example` |
| `AI_GATEWAY_CORS_ORIGIN` vs `CORS_ORIGIN` | ai-gateway reads `CORS_ORIGIN` from env, but docs and `.env.example` use `AI_GATEWAY_CORS_ORIGIN` | Standardize on `AI_GATEWAY_CORS_ORIGIN` |
| `AGENT_TEST_FAILURE_INJECTION` | Used in agent-provider and zarvis-owner-voice compose | Document as global test flag |
| `ZC_ENVIRONMENT` | Used in `docker-compose.phase6.yml` | Document as phase6-only |

## Dangerous defaults

| Variable | Current Default | Risk | Recommendation |
|---|---|---|---|
| `HOST` | `127.0.0.1` | Safe for local, but some services override to `0.0.0.0` in Docker | Document override policy |
| `PORT` | Service-specific | Safe | — |
| `LOG_LEVEL` | `info` | Safe | — |

## Browser-exposed secrets

**None found.** CI `validate.yml` enforces that `apps/**` does not reference `Z_PLATFORM_SERVICE_TOKEN`, `AI_GATEWAY_PROVIDER_TOKEN`, `UPSTREAM_API_KEY`, or `PROVIDER_TOKEN` in public-facing env vars or bundles.

## Production fail-closed

Variables that must fail clearly when missing in production:
- `Z_PLATFORM_SERVICE_TOKEN`
- `REDIS_URL` (ai-gateway, phase6-api, zc)
- `VOICE_TICKET_SECRET` (voice-gateway)
- `ZARVIS_EDGE_SHARED_SECRET` (zarvis services)
- `ZARVIS_*_WORKER_TOKEN` (zarvis services)
- `ZARVIS_*_MASTER_KEY_B64` (zarvis-memory, zarvis-perception)

Current behavior: most services start without these and fail at first request. **Target:** fail at startup with clear error message.
