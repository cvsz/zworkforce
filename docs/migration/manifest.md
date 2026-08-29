# Migration Manifest

Source repository: `cvsz/zeaz-platform`

## Phase 0 - Foundation

| Item | Target | Action | Status |
|---|---|---|---|
| Repository policies | root | Recreate security-first policy | complete |
| Workspace configuration | root | Create clean pnpm workspace | complete |
| Architecture and migration docs | docs | Create baseline documentation | complete |

## Phase 1 - AI foundation

| Item | Target | Action | Status |
|---|---|---|---|
| ZAI Coder application boundary | `apps/zaicoder` | Establish packaging, safe configuration and gateway contract | complete |
| AI gateway boundary | `services/ai-gateway` | Establish ownership and safe runtime configuration | complete |
| Streaming, MCP and model preflight runtime | `apps/zaicoder/backend` | Migrate tested isolated modules and regression tests | complete |
| Gateway-backed CLI | `apps/zaicoder/backend` | Add OpenAI-compatible client, command entry point and unit tests | complete |
| Browser gateway proxy and terminal shell | `apps/zaicoder/web` | Add server-side gateway proxy, input validation and basic browser UI | complete |
| Browser response streaming | `apps/zaicoder/web` | Add end-to-end SSE proxying and browser delta rendering | complete |
| Browser file upload proxy | `apps/zaicoder/web` | Proxy uploads through the platform gateway without exposing provider credentials | complete |
| Persistent project/workspace metadata | `apps/zaicoder/web` + workspace runtime | Add adapter boundary, file-backed default, HTTP durable metadata adapter, owner enforcement, retention timestamps, cleanup runner, and uploaded-file links | complete |
| Provider attachment adapters | `services/ai-gateway` | Add adapter registry, provider selection, OpenAI-compatible binary/content upload pass-through, and Anthropic unsupported-upload guardrails | complete |
| Hugging Face model catalog | `services/ai-gateway` | Add curated free/local model metadata and protected `/v1/models` listing | complete |

## Phase 2 - Agent orchestration

| Item | Target | Action | Status |
|---|---|---|---|
| Agent job event contracts | `packages/contracts` | Define requested, approved, and completed lifecycle events with schemas and tests | complete |
| Durable job store and queue adapter | `services/agent-orchestrator` | Persist job state and enqueue approved execution work through replaceable adapters | complete |
| Tool grant approval policy | `services/agent-orchestrator` | Require explicit scoped grants before mutating tool execution | complete |
| Sandboxed worker runtime | `services/agent-orchestrator` | Execute jobs with resource limits, retries, cancellation, and audit hooks | complete |
| Production provider adapters | `services/agent-orchestrator` | Require operator-approved database, queue, observability, identity, and sandbox providers before external traffic | complete |

## Phase 3 - ZChat migration

| Item | Target | Action | Status |
|---|---|---|---|
| ZChat presentation shell | `apps/zchat` | Keep thin browser UI and server-side gateway proxy only | complete |
| ZChat model catalog | `apps/zchat` | Load models from the AI Gateway instead of browser provider config | complete |
| ZChat identity and correlation | `apps/zchat` | Forward tenant, conversation, request, and usage-correlation identifiers | complete |
| ZChat session and streaming | `apps/zchat` | Add streaming proxy, logout, session expiry, and accessibility-oriented UI tests | complete |

## Phase 4 - Generator and workspace migration

| Item | Target | Action | Status |
|---|---|---|---|
| Audited generator templates | `tools/zai-factory` | Add safe template manifest, validation, and generator tests | complete |
| Generated-file ownership | `tools/zai-factory` + `services/workspace-runtime` | Require generated files to declare generator ownership and reject secret-bearing paths | complete |
| ZOW workspace split | `apps/zow` + `services/workspace-runtime` | Keep ZOW as UI/proxy and move execution decisions to isolated runtime | complete |
| Shell/deploy approval policy | `services/workspace-runtime` | Require explicit `shell` or `deploy` approval grants before accepting execution requests | complete |

## Phase 5 - Usage and billing boundary

| Item | Target | Action | Status |
|---|---|---|---|
| AI usage events | `services/ai-gateway` + `packages/contracts` | Emit immutable `ai.usage.recorded.v1` records server-side | complete |
| Billing ledger idempotency | `services/billing-ledger` | Validate idempotency keys before ledger entries | complete |
| Credits and invoice intents | `services/billing-ledger` | Implement tenant credits and invoice-intent boundary | complete |
| ZWallet audited adapter | `apps/zwallet` | Forward only credits and invoice intents; reject signing, cards, KYC, MPC, and swaps | complete |

## Phase 6 - Platform operations

| Item | Target | Action | Status |
|---|---|---|---|
| CI and security gates | `.github/workflows` + `tools/ops` | Add runtime tests, dependency checks, and secret scanning | complete |
| SBOM and provenance | `tools/ops` + operations workflow | Generate SPDX SBOM and verify package provenance metadata | complete |
| Cloudflare Access policies | `docs/operations` | Define service-to-service policy map and deny rules | complete |
| Observability and runbooks | `docs/operations` | Document health, logs, metrics, traces, backups, restore, and incidents | complete |
| Staging readiness | `docs/operations/staging-readiness.md` | Add pre-production review checklist | complete |

## Candidate migrations

| Legacy source | Target | Selection rule | Status |
|---|---|---|---|
| `apps/zchat` | `apps/zchat` | Retain UI only; replace direct provider keys with platform gateway | complete |
| `apps/zai-stack` | `services/agent-orchestrator` | Extract policy and job-routing runtime | partial |
| `apps/zai-factory` | `tools/zai-factory` | Retain audited skills, generators and templates only | complete |
| `apps/zow` | `apps/zow` + `services/workspace-runtime` | Split UI from sandbox/runtime | complete |
| `apps/zwallet` | `apps/zwallet` + `services/billing-ledger` | Keep UI/ledger adapters; exclude signing and production provider config | complete |

## Status definitions

- `complete`: the migrated unit has code, docs, tests or CI coverage, and no known required runtime dependency on the legacy repository.
- `partial`: the platform boundary exists, but durable storage, production provider translation, identity, tests, or operational wiring remains.
- `pending`: no runtime migration has been accepted yet.

A runtime component is copied only after its dependency list, test command, secret scan, license status, and rollback plan are recorded.
