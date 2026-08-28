# Feature Ownership Matrix

## AI Gateway

| Feature | Domain | Owner | Source | Public API | Data Owner | Contracts | Dependencies | Security Boundary | Prod Status | Tests | Observability | Operator Deps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Provider credential pool | AI | `services/ai-gateway` | `services/ai-gateway/index.js` | Redis `provider:<name>:active_keys` | ai-gateway | — | Redis | Server-side only, never in browser | IMPLEMENTED | Unit | Pino logs, redacted | Provider keys |
| Model catalog | AI | `services/ai-gateway` | `services/ai-gateway/index.js` | `GET /v1/models` | ai-gateway | — | Env | Bearer token | IMPLEMENTED | Unit | Pino logs | — |
| Chat completions proxy | AI | `services/ai-gateway` | `services/ai-gateway/index.js` | `POST /v1/chat/completions` | ai-gateway | — | Upstream provider, Redis | Bearer token, rate limit | IMPLEMENTED | Unit | Pino logs, latency | Provider keys |
| Anthropic messages proxy | AI | `services/ai-gateway` | `services/ai-gateway/index.js` | `POST /v1/messages` | ai-gateway | — | Anthropic upstream, Redis | Bearer token, rate limit | IMPLEMENTED | Unit | Pino logs | Anthropic key |
| Streaming | AI | `services/ai-gateway` | `services/ai-gateway/index.js` | SSE pipe | ai-gateway | — | Upstream provider | Bearer token | IMPLEMENTED | Unit | Pino logs | — |
| Usage emission | AI | `services/ai-gateway` | (emitted via event, not in repo) | Event | billing-ledger | `ai.usage.recorded.v1` | Redis | Internal | IMPLEMENTED | — | Metrics | billing-ledger |
| Quota / rate limit | AI | `services/ai-gateway` | `services/ai-gateway/security-config.mjs` | `express-rate-limit` | ai-gateway | — | Redis (via provider pool) | Bearer token | IMPLEMENTED | Unit | Pino logs | — |
| Provider fallback | AI | `services/ai-gateway` | `services/ai-gateway/index.js` | Retry loop | ai-gateway | — | Upstream providers | Bearer token | IMPLEMENTED | Unit | Pino logs | Provider keys |
| Upload / attachment | AI | `services/ai-gateway` | (not implemented in current index.js) | — | — | — | — | — | PENDING_IMPLEMENTATION | — | — | — |

## Agent Orchestrator

| Feature | Domain | Owner | Source | Public API | Data Owner | Contracts | Dependencies | Security Boundary | Prod Status | Tests | Observability | Operator Deps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Job submission | Agent | `services/agent-orchestrator` | `services/agent-orchestrator/server.mjs` | `POST /v1/jobs` | agent-provider | `agent.job.requested.v1` | agent-provider | Bearer token, idempotency | IMPLEMENTED | Unit | Pino logs | — |
| Job approval | Agent | `services/agent-orchestrator` | `services/agent-orchestrator/server.mjs` | `POST /v1/jobs/:id/approve` | agent-provider | `agent.job.approved.v1` | agent-provider, identity | Bearer token, approval grant | IMPLEMENTED | Unit | Pino logs | Identity provider |
| Job cancellation | Agent | `services/agent-orchestrator` | `services/agent-orchestrator/server.mjs` | `POST /v1/jobs/:id/cancel` | agent-provider | `agent.job.completed.v1` | agent-provider | Bearer token | IMPLEMENTED | Unit | Pino logs | — |
| Job retry | Agent | `services/agent-orchestrator` | `services/agent-orchestrator/server.mjs` | `POST /v1/jobs/:id/retry` | agent-provider | — | agent-provider | Bearer token | IMPLEMENTED | Unit | Pino logs | — |
| Worker dispatch | Agent | `services/agent-orchestrator` | `services/agent-orchestrator/server.mjs` | `POST /v1/worker/run-next` | agent-provider | — | agent-provider, sandbox | Bearer token | IMPLEMENTED | Unit | Pino logs | Sandbox runtime |
| Durable job store | Agent | `services/agent-provider` | `services/agent-provider/server.mjs` | `GET/PUT /jobs/:id` | agent-provider | — | File system | Bearer token | IMPLEMENTED | Unit | Prometheus metrics | Disk |
| Queue | Agent | `services/agent-provider` | `services/agent-provider/server.mjs` | `POST /queue`, `POST /queue/next` | agent-provider | — | File system | Bearer token | IMPLEMENTED | Unit | Prometheus metrics | Disk |
| Audit events | Agent | `services/agent-provider` | `services/agent-provider/server.mjs` | `POST /events` | agent-provider | — | File system | Bearer token | IMPLEMENTED | Unit | Prometheus metrics | Disk |
| Workspace metadata | Agent | `services/agent-provider` | `services/agent-provider/server.mjs` | `GET/PUT /workspaces/:id` | agent-provider | — | File system | Bearer token | IMPLEMENTED | Unit | Prometheus metrics | Disk |
| Backup / restore | Agent | `services/agent-provider` | `services/agent-provider/server.mjs` | `GET /backup/export`, `POST /backup/restore`, `GET /backup/verify` | agent-provider | — | File system | Bearer token | IMPLEMENTED | Unit | Prometheus metrics | Disk |

## Workspace Runtime

| Feature | Domain | Owner | Source | Public API | Data Owner | Contracts | Dependencies | Security Boundary | Prod Status | Tests | Observability | Operator Deps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Project validation | Workspace | `services/workspace-runtime` | `services/workspace-runtime/server.mjs` | `POST /v1/projects/validate` | workspace-runtime | — | — | Bearer token | IMPLEMENTED | Unit | Pino logs | — |
| Shell request | Workspace | `services/workspace-runtime` | `services/workspace-runtime/server.mjs` | `POST /v1/shell` | workspace-runtime | — | — | Bearer token, approval grant | IMPLEMENTED | Unit | Pino logs | Approval authority |
| Deploy request | Workspace | `services/workspace-runtime` | `services/workspace-runtime/server.mjs` | `POST /v1/deploy` | workspace-runtime | — | — | Bearer token, approval grant | IMPLEMENTED | Unit | Pino logs | Approval authority |

## Billing Ledger

| Feature | Domain | Owner | Source | Public API | Data Owner | Contracts | Dependencies | Security Boundary | Prod Status | Tests | Observability | Operator Deps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Usage recording | Billing | `services/billing-ledger` | `services/billing-ledger/server.mjs` | `POST /v1/usage` | billing-ledger | `ai.usage.recorded.v1` | — | Bearer token, idempotency | IMPLEMENTED | Unit | Pino logs | — |
| Credit management | Billing | `services/billing-ledger` | `services/billing-ledger/server.mjs` | `POST /v1/credits` | billing-ledger | — | — | Bearer token | IMPLEMENTED | Unit | Pino logs | — |
| Invoice intents | Billing | `services/billing-ledger` | `services/billing-ledger/server.mjs` | `POST /v1/invoice-intents` | billing-ledger | — | — | Bearer token | IMPLEMENTED | Unit | Pino logs | — |

## ZWallet

| Feature | Domain | Owner | Source | Public API | Data Owner | Contracts | Dependencies | Security Boundary | Prod Status | Tests | Observability | Operator Deps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Invoice intent adapter | Billing | `apps/zwallet` | `apps/zwallet/server.mjs` | `POST /api/invoice-intents` | billing-ledger | — | billing-ledger | Bearer token, forbidden key rejection | IMPLEMENTED | Unit | Pino logs | billing-ledger |
| Credit adapter | Billing | `apps/zwallet` | `apps/zwallet/server.mjs` | `POST /api/credits` | billing-ledger | — | billing-ledger | Bearer token, forbidden key rejection | IMPLEMENTED | Unit | Pino logs | billing-ledger |

## ZChat

| Feature | Domain | Owner | Source | Public API | Data Owner | Contracts | Dependencies | Security Boundary | Prod Status | Tests | Observability | Operator Deps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Chat proxy | AI | `apps/zchat` | `apps/zchat/server.mjs` | `POST /api/chat` | ai-gateway | — | ai-gateway | Bearer token | IMPLEMENTED | Unit | Pino logs | ai-gateway |
| Stream proxy | AI | `apps/zchat` | `apps/zchat/server.mjs` | `POST /api/chat/stream` | ai-gateway | — | ai-gateway | Bearer token | IMPLEMENTED | Unit | Pino logs | ai-gateway |
| Model listing | AI | `apps/zchat` | `apps/zchat/server.mjs` | `GET /api/models` | ai-gateway | — | ai-gateway | Bearer token | IMPLEMENTED | Unit | Pino logs | ai-gateway |
| Platform status | Platform | `apps/zchat` | `apps/zchat/server.mjs` | `GET /api/platform/status` | zc, phase6-api | — | zc, phase6-api | Bearer token | IMPLEMENTED | Unit | Pino logs | zc, phase6-api |

## ZOW

| Feature | Domain | Owner | Source | Public API | Data Owner | Contracts | Dependencies | Security Boundary | Prod Status | Tests | Observability | Operator Deps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Project validation proxy | Workspace | `apps/zow` | `apps/zow/server.mjs` | `POST /api/projects/validate` | workspace-runtime | — | workspace-runtime | Bearer token | IMPLEMENTED | Unit | Pino logs | workspace-runtime |
| Shell proxy | Workspace | `apps/zow` | `apps/zow/server.mjs` | `POST /api/shell` | workspace-runtime | — | workspace-runtime | Bearer token | IMPLEMENTED | Unit | Pino logs | workspace-runtime |
| Deploy proxy | Workspace | `apps/zow` | `apps/zow/server.mjs` | `POST /api/deploy` | workspace-runtime | — | workspace-runtime | Bearer token | IMPLEMENTED | Unit | Pino logs | workspace-runtime |

## ZVoice

| Feature | Domain | Owner | Source | Public API | Data Owner | Contracts | Dependencies | Security Boundary | Prod Status | Tests | Observability | Operator Deps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Voice session | Voice | `apps/zvoice` | `apps/zvoice/server.mjs` | `POST /api/voice/session` | voice-gateway | — | voice-gateway | Bearer token | IMPLEMENTED | Unit | Pino logs | voice-gateway |
| ZARVIS command bridge | Voice | `apps/zvoice` | `apps/zvoice/server.mjs` | `POST /api/zarvis/command` | zarvis-orchestrator | `zarvis.command.requested.v1` | zarvis-orchestrator | Owner edge secret, service token | IMPLEMENTED | Unit | Pino logs | zarvis-orchestrator |
| Local conversation fallback | Voice | `apps/zvoice` | `apps/zvoice/local-conversation.mjs` | Internal | local LLM | — | Ollama / llama.cpp / LM Studio | Local only | IMPLEMENTED | Unit | Pino logs | Local LLM |

## ZAI Coder

| Feature | Domain | Owner | Source | Public API | Data Owner | Contracts | Dependencies | Security Boundary | Prod Status | Tests | Observability | Operator Deps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Chat proxy | AI | `apps/zaicoder/web` | `apps/zaicoder/web/server/gateway.mjs` | `POST /api/chat` | ai-gateway | — | ai-gateway | Bearer token | IMPLEMENTED | Unit | Pino logs | ai-gateway |
| Stream proxy | AI | `apps/zaicoder/web` | `apps/zaicoder/web/server/gateway.mjs` | `POST /api/chat/stream` | ai-gateway | — | ai-gateway | Bearer token | IMPLEMENTED | Unit | Pino logs | ai-gateway |
| File forward | AI | `apps/zaicoder/web` | `apps/zaicoder/web/server/gateway.mjs` | `POST /api/files` | ai-gateway | — | ai-gateway | Bearer token | IMPLEMENTED | Unit | Pino logs | ai-gateway |
| Workspace metadata adapter | Workspace | `apps/zaicoder/web` | `apps/zaicoder/web/server/workspace-store.mjs` | Internal | External metadata | — | Workspace metadata URL | Bearer token | IMPLEMENTED | Unit | Pino logs | — |
| CLI | Platform | `apps/zaicoder/backend` | `apps/zaicoder/backend/src/zaicoder/cli.py` | CLI | — | — | — | — | IMPLEMENTED | pytest | — | — |

## Zarvis Local Services

| Feature | Domain | Owner | Source | Public API | Data Owner | Contracts | Dependencies | Security Boundary | Prod Status | Tests | Observability | Operator Deps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Command execution | Zarvis | `services/zarvis-orchestrator` | `services/zarvis-orchestrator/src/orchestrator.mjs` | `POST /v1/commands` | zarvis-orchestrator | `zarvis.command.requested.v1`, `zarvis.command.completed.v1` | File session store | Owner edge secret, service token | IMPLEMENTED | Unit | Stdout audit | — |
| Session management | Zarvis | `services/zarvis-orchestrator` | `services/zarvis-orchestrator/src/session-store.mjs` | `GET /v1/sessions/:id`, `DELETE /v1/sessions/:id` | zarvis-orchestrator | `zarvis.session.event.v1` | File system | Owner edge secret | IMPLEMENTED | Unit | Stdout audit | Disk |
| Task plans | Zarvis | `services/zarvis-task-gateway` | `services/zarvis-task-gateway/runtime.mjs` | `POST /v1/tasks` | zarvis-task-gateway | `zarvis.task.requested.v1`, `zarvis.task.approval.v1` | File system | Owner edge secret, worker token | IMPLEMENTED | Unit | Stdout audit | Disk |
| Memory store | Zarvis | `services/zarvis-memory` | `services/zarvis-memory/runtime.mjs` | `POST /v1/memory/proposals` | zarvis-memory | `zarvis.memory.proposal.v1`, `zarvis.memory.snapshot.v1` | Encrypted file store | Owner edge secret, worker token | IMPLEMENTED | Unit | Stdout audit | Disk |
| Action preview/rollback | Zarvis | `services/zarvis-action-gateway` | `services/zarvis-action-gateway/runtime.mjs` | `POST /v1/actions/preview` | zarvis-action-gateway | `zarvis.action.preview.v1`, `zarvis.action.result.v1` | File system | Owner edge secret, worker token | IMPLEMENTED | Unit | Stdout audit | Disk |
| Proactive scheduler | Zarvis | `services/zarvis-proactive` | `services/zarvis-proactive/runtime.mjs` | `GET /v1/status`, `PUT /v1/policy` | zarvis-proactive | `zarvis.proactive.signal.v1`, `zarvis.proactive.notification.v1` | File system, local health adapter | Owner token, worker token, loopback only | IMPLEMENTED | Unit | Stdout audit | Disk |
| Perception sessions | Zarvis | `services/zarvis-perception` | `services/zarvis-perception/runtime.mjs` | `POST /v1/perception/sessions` | zarvis-perception | `zarvis.perception.session.v1`, `zarvis.perception.result.v1` | Encrypted file store | Owner edge secret, worker token | IMPLEMENTED | Unit | Stdout audit | Disk |
| Voice edge | Zarvis | `services/zarvis-owner-voice-edge` | `services/zarvis-owner-voice-edge/server.mjs` | HTTP edge | — | — | — | Edge secret | IMPLEMENTED | — | — | — |

## ZC / zcoder

| Feature | Domain | Owner | Source | Public API | Data Owner | Contracts | Dependencies | Security Boundary | Prod Status | Tests | Observability | Operator Deps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| FastAPI API | Platform | `services/zc` | `services/zc/app/main.py` | REST + gRPC | zc | — | Redis, Cloudflare | Bearer token | IMPLEMENTED | pytest | OTel, Prometheus | Redis |
| CLI | Platform | `services/zc` | `services/zc/app/cli.py` | CLI | — | — | — | — | IMPLEMENTED | pytest | — | — |
| Webapp | Platform | `services/zc` | `services/zc/webapp/` | Frontend | — | — | — | — | IMPLEMENTED | — | — | — |
| Control panel | Platform | `services/zc` | `services/zc/app/api/control_panel.py` | REST | zc | — | — | Bearer token | IMPLEMENTED | pytest | — | — |
| AI routes | AI | `services/zc` | `services/zc/app/api/v1/ai_routes.py` | REST | zc | — | ai-gateway | Bearer token | IMPLEMENTED | pytest | — | ai-gateway |
| Chat routes | AI | `services/zc` | `services/zc/app/api/v1/chat_routes.py` | REST | zc | — | ai-gateway | Bearer token | IMPLEMENTED | pytest | — | ai-gateway |
| Resource routes | Platform | `services/zc` | `services/zc/app/api/v1/resource_routes.py` | REST | zc | — | — | Bearer token | IMPLEMENTED | pytest | — | — |
| Delta sync | Platform | `services/zc` | `services/zc/app/services/delta/sync_service.py` | Internal | zc | — | External | — | IMPLEMENTED | pytest | — | — |
| Workers | Platform | `services/zc` | `services/zc/app/workers/` | Internal | zc | — | — | — | IMPLEMENTED | pytest | — | — |

## Z-Prov

| Feature | Domain | Owner | Source | Public API | Data Owner | Contracts | Dependencies | Security Boundary | Prod Status | Tests | Observability | Operator Deps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Provider management | AI | `services/z-prov` | `services/z-prov/app/` | REST | z-prov | — | Supabase, Cloudflare | Bearer token, WIF | IMPLEMENTED | pytest | — | Supabase, Cloudflare |
| Control adapters | Platform | `services/z-prov` | `services/z-prov/app/` | Internal | z-prov | — | — | — | IMPLEMENTED | pytest | — | — |
| Sandbox egress | Platform | `services/z-prov` | `services/z-prov/app/` | Internal | z-prov | — | — | Loopback only | IMPLEMENTED | pytest | — | — |
| Enterprise vault | Platform | `services/z-prov` | `services/z-prov/app/` | Internal | z-prov | — | — | Encrypted | IMPLEMENTED | pytest | — | — |

## Phase6 / ZC

| Feature | Domain | Owner | Source | Public API | Data Owner | Contracts | Dependencies | Security Boundary | Prod Status | Tests | Observability | Operator Deps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| External AI verification | AI | `services/phase6-api` | `services/phase6-api/app.py` | `POST /ai/upload`, `/ai/failover`, `/ai/stream`, `/ai/providers/verify` | phase6-api | — | Upstream providers, Redis | Bearer token | IMPLEMENTED | pytest | Prometheus metrics | Provider keys |
| Supabase read bridge | Platform | `services/phase6-api` | `services/phase6-api/app.py` | `GET /supabase/read` | Supabase | — | Supabase | Bearer token, URL validation | IMPLEMENTED | pytest | Prometheus metrics | Supabase project |
| GitHub webhook | Platform | `services/phase6-api` | `services/phase6-api/app.py` | `POST /webhooks/github` | phase6-api | — | Redis | HMAC signature | IMPLEMENTED | pytest | Prometheus metrics | GitHub webhook secret |
| ZC API | Platform | `services/zc` | `services/zc/app/main.py` | gRPC + REST | zc | — | Redis | Bearer token | IMPLEMENTED | pytest | — | Redis |

## Voice Stack

| Feature | Domain | Owner | Source | Public API | Data Owner | Contracts | Dependencies | Security Boundary | Prod Status | Tests | Observability | Operator Deps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Ticket issuance | Voice | `services/voice-gateway` | `services/voice-gateway/index.mjs` | `POST /v1/voice/tickets` | voice-gateway | — | — | Bearer token | IMPLEMENTED | Unit | Pino logs | — |
| WebSocket upgrade | Voice | `services/voice-gateway` | `services/voice-gateway/index.mjs` | `GET /v1/realtime` (Upgrade) | voice-gateway | — | voice-agent | Ticket signature | IMPLEMENTED | Unit | Pino logs | voice-agent |
| Local speech pipeline | Voice | `services/voice-agent` | `services/voice-agent/` | Internal | voice-agent | — | Hugging Face models | Loopback only | IMPLEMENTED | — | — | Local GPU/CPU |

## Agent Control Worker

| Feature | Domain | Owner | Source | Public API | Data Owner | Contracts | Dependencies | Security Boundary | Prod Status | Tests | Observability | Operator Deps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Agent control | Agent | `workers/agent-control-worker` | `workers/agent-control-worker/src/index.ts` | Cloudflare Worker | — | — | — | Cloudflare Access | IMPLEMENTED | — | — | Cloudflare |

## Platform Contracts

| Feature | Domain | Owner | Source | Public API | Data Owner | Contracts | Dependencies | Security Boundary | Prod Status | Tests | Observability | Operator Deps |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Cross-service schemas | Platform | `packages/contracts` | `packages/contracts/schemas/*.schema.json` | JSON Schema | contracts | All v1 schemas | — | — | IMPLEMENTED | Node test | — | — |
