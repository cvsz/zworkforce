# Z.A.R.V.I.S. Upgrade Roadmaps

**Status:** active forward roadmap  
**Scope:** `cvsz/zworkforce` with the consolidated Z.A.R.V.I.S. suite under `packages/zarvis`  
**Reference implementations studied:** `open-jarvis/OpenJarvis` (Apache-2.0) and publicly documented Skywork workspace-agent capabilities

> `ROADMAP.md` remains the release-history and production-readiness roadmap. This file is the forward feature roadmap for the Z.A.R.V.I.S. assistant experience, workspace-agent UX, and architecture refactors.

## 1. Baseline

zWorkforce already contains a substantial Z.A.R.V.I.S. implementation:

- `packages/zarvis/apps/zvoice` provides the realtime browser voice surface;
- `services/voice-gateway` issues short-lived WebSocket tickets;
- `services/voice-agent` owns VAD/STT/LLM/TTS processing;
- `services/zarvis-orchestrator` owns command routing and speech-ready results;
- `services/zarvis-task-gateway` and `services/zarvis-action-gateway` preserve approval boundaries;
- memory, perception, proactive services, contracts, Windows and console surfaces already exist;
- the root control-plane frontend is served from `zworkforce/static`.

The upgrade therefore **must refactor and compose existing primitives rather than add a second assistant stack**.

## 2. Architecture concepts to adopt

Adopt architectural/product ideas, not wholesale source imports:

1. **Config-driven system composition** — one builder/factory composes model, tools, skills, memory, speech, scheduling and policy.
2. **Typed registry/discovery** — pluggable STT, TTS, model, tool, skill and agent providers with explicit health/capabilities.
3. **Skills as first-class invokable capabilities** — discoverable catalog, dependency validation, policy checks, tool wrapping and trace evidence.
4. **Agent execution modes** — on-demand, scheduled and continuous operators with persistent state.
5. **Trace-driven improvement** — evaluate latency, quality, cost and energy before changing routing or skill selection.
6. **Workspace-first task continuity** — durable projects/conversations, context budget/compaction, artifacts, review state and subagent visibility.
7. **Isolated local execution** — scoped workspace roots plus bounded git branch/worktree operations rather than unrestricted host access.
8. **Governed skill lifecycle** — immediate activation inside the existing capability envelope, safe update, disable/enable and rollback.
9. **Operator-facing FinOps** — preflight budget checks and durable usage/chargeback drilldown.

Keep zWorkforce's stronger existing security boundaries: server-side secrets, tenant isolation, approval-scoped mutation, durable idempotency and audited action gateways.

Research evidence and the full Skywork-derived map are maintained in `docs/SKYWORK-CHANGELOG-REVERSE-ENGINEERING.md`. The executable cross-subsystem plan is `planning/exec-planning-skywork.md`.

## 3. Roadmap

### R0 — Architecture and compatibility contract

- [x] Record the OpenJarvis-to-Z.A.R.V.I.S. file mapping in `packages/zarvis/docs/architecture/openjarvis-upgrade-map.md`.
- [x] Keep Apache-2.0 attribution for any source material actually adapted.
- [x] Define a browser-safe voice contract that contains no provider/service credentials.
- [x] Define one canonical Z.A.R.V.I.S. conversation state machine:
  `idle -> arming -> listening -> transcribing -> thinking -> speaking -> idle`, plus `muted`, `interrupted`, `approval_required`, and `error` substates.
- [x] Preserve existing `zarvis.command.requested.v1` and approval/action contracts unless a versioned migration is required.

### R1 — Z.A.R.V.I.S. CARD in the zWorkforce frontend

Goal: talk to Z.A.R.V.I.S. directly from the AI Workforce control plane.

- [x] Add a dedicated `Z.A.R.V.I.S.` dashboard card in `zworkforce/static/index.html`.
- [x] Add a GPU-friendly animated AI orb with state-driven animation in `zworkforce/static/styles.css`.
- [x] Add push-to-talk to `zworkforce/static/app.js`:
  - pointer/touch press-and-hold;
  - `Space` press-and-hold when focus is not in an editable control;
  - explicit microphone permission state;
  - keyboard-accessible toggle fallback;
  - barge-in/cancel while Z.A.R.V.I.S. is speaking.
- [x] Show live state, partial/final transcript, last reply, runtime/model label, microphone state and approval-required state.
- [x] Reuse/extract the existing ZVoice PCM16/AudioWorklet realtime client instead of embedding ZVoice in an iframe.
- [x] Keep credentials server-side through a zWorkforce BFF/session endpoint.
- [x] Respect `prefers-reduced-motion` and provide a non-animated accessible state representation.

**R1 acceptance:** an authenticated control-plane user can hold PTT, speak, see the orb move through listening/thinking/speaking states, hear the answer, interrupt playback, and never receive an upstream credential.

### R2 — Shared browser voice client

- [x] Extract browser-safe capture/session/event logic from `apps/zvoice/public/app.js` into a shared Z.A.R.V.I.S. voice-client package.
- [x] Keep AudioWorklet PCM16 capture at 16 kHz and realtime interruption semantics.
- [x] Make ZVoice and the dashboard card consume the same client contract.
- [x] Add contract tests for session lifecycle, interruption, reconnect, ticket expiry and microphone denial.
- [x] Ensure the shared library cannot accept or serialize service/provider secrets.

### R3 — Speech provider registry

Refactor the voice runtime toward a typed registry while keeping the current service boundary.

- [x] Define STT provider interface: `transcribe/stream`, languages, sample-rate support, health and local/cloud classification.
- [x] Define TTS provider interface: `synthesize/stream`, voices, sample rates, health and local/cloud classification.
- [x] Register existing local speech implementation first.
- [x] Add optional adapters for Faster Whisper / Whisper-compatible STT and local TTS implementations already supported by deployment profiles.
- [x] Permit hosted providers only through server-side configuration and policy.
- [x] Surface provider health/capabilities to operators without exposing secrets.

### R4 — Z.A.R.V.I.S. skills runtime

- [x] Maintain a runtime skill manifest/catalog distinct from repository coding-agent skills under `.agents/skills`.
- [x] Each runtime skill declares: ID/version, description, required capabilities, allowed tools, mutability, approval policy, timeout, retry/idempotency behavior and input/output schema.
- [x] Discover skills deterministically with first-class validation and duplicate rejection.
- [x] Wrap skills behind the same policy/tool-execution boundary as normal tools.
- [x] Add skill dependency validation and bounded nested invocation.
- [x] Add active-version resolution, enable/disable, safe system-skill auto-update and explicit rollback foundation.
- [x] Reject automatic updates that silently add tool capabilities, escalate read→write mutability or weaken approval requirements.
- [ ] Persist complete lifecycle/trace state through the durable repository and prove restart-safe recovery for every lifecycle transition.
- [ ] Integrate signed remote marketplace packages through the existing skill-registry trust boundary.
- [x] Never auto-promote trace-mined/repeated-workflow skills into production; generated candidates require review and tests.

### R5 — Agent manager and execution modes

- [x] Normalize Z.A.R.V.I.S. agent manifests around three modes: `on_demand`, `scheduled`, `continuous`.
- [x] Add `voice-orchestrator` for low-latency spoken-turn routing.
- [x] Add `operator-supervisor` for heartbeat, stalled-run detection, rate limits and safe recovery.
- [x] Reuse existing specialist agents such as chief-of-staff, memory, code and review agents rather than cloning them.
- [x] Persist agent state/version, enforce capability policy, rate limits and max-concurrency.
- [x] Add event-driven triggers using existing durable scheduler/event infrastructure.
- [x] Add versioned rollout/rollback and failure budgets for continuous agents.

### R6 — Memory, context and conversation continuity

- [x] Bind voice sessions to tenant/subject-scoped conversation state.
- [x] Add durable project/conversation IDs, search, pin/archive and stable history navigation foundation.
- [ ] Expose context-budget state per conversation/model.
- [ ] Implement explicit compaction that creates a versioned summary artifact instead of silently rewriting history.
- [x] Retrieve only authorized memory and redact sensitive content before model/tool boundaries.
- [x] Separate ephemeral transcript context from durable memory writes.
- [x] Require explicit retention/consent policy for durable voice-derived memory.
- [x] Provide “forget this conversation” / deletion flows with auditable completion.

### R7 — Proactive Z.A.R.V.I.S.

- [x] Enable scheduled/continuous agents only with explicit subscriptions.
- [x] Add quiet hours, notification policy, rate limits and deduplication.
- [ ] Add tenant-scoped notification center for completion, approval, questions, failures, budget risk and stalled agents.
- [x] Add health/heartbeat telemetry and stalled-operator detection.
- [x] Route requests needing human authorization into the existing approval system rather than executing mutation autonomously.

### R8 — Intelligent local/cloud routing

- [x] Add query complexity classification and explicit local-first routing policy.
- [x] Add redaction-before-cloud and taint-aware policy checks.
- [x] Track latency, cost, quality and energy per route.
- [x] Support operator-configured failover without silent provider substitution for pinned workloads.
- [x] Keep cloud transmission disabled for protected data unless policy explicitly permits it.

### R8.1 — OpenRouter & Enterprise Model Gateway Integration (Free Model First)

- [x] Unified OpenAI-Compatible Router Gateway (`http://api:9569/v1`) with server-side credentials and rate-limit safety.
- [x] **Free Model First Routing Architecture**:
  - Primary dispatch defaults to OpenRouter Free Models Router (`openrouter/free`) and explicit `:free` variants (`meta-llama/llama-3.3-70b-instruct:free`, `deepseek/deepseek-r1:free`, `google/gemini-2.0-flash-lite:free`, `qwen/qwen-2.5-coder-32b-instruct:free`);
  - Multi-tier zero-cost fallback chain: `openrouter/free` → Groq Free Quota (`llama-3.3-70b`) → Local Edge (Ollama/vLLM) → Paid Escalation (Sol tier);
  - Dynamic capability filtering: automatic selection of free models matching required modalities (vision, tool calling, structured JSON output).
- [x] OpenRouter Multi-Provider Failover: support automatic failover across 600+ hosted models (Anthropic, OpenAI, Google, DeepSeek, Groq, Meta, Mistral, Moonshot).
- [x] Dynamic Provider & Privacy Routing: honor zero-data-retention (ZDR) flags, privacy toggles, data-training policies, and allowed provider routing constraints without breaking tenant isolation.
- [x] Open WebUI Enterprise Control Center integration (`:3080`): interactive chat, dual model arena, interactive code artifacts, RAG knowledge, and OpenAPI tool/function dispatch.
- [x] Smart Model Variant Slugs & Specialized Routing:
  - `:free` (Free Models Router primary tier with zero token cost);
  - `:thinking` / Extended Reasoning variant handling across free DeepSeek-R1, Claude, and OpenAI o-series;
  - `:exacto` & Auto-Exacto provider sorting for quality-optimized tool/function calling;
  - `:nitro` for ultra-low latency inference;
  - `:extended` for large context window retention;
  - `:online` for model-agnostic web search grounding;
  - Pareto Router (minimum coding benchmark routing without pinning static model slugs);
  - Fusion Router & Multi-Model Deliberation (synthesizing consensus outputs from parallel challenger models).
- [ ] Model Migration & Parameter Modernization:
  - Claude Opus 5 / Claude 5 Sonnet / Claude 4.7 / Claude 4.6 migration alignment (adaptive thinking, xhigh/max effort levels, sampling parameter deprecations, mid-conversation tool mutations);
  - GPT-5.6 / GPT-5.5 / GPT-5.4 adoption (`reasoning.mode`, `reasoning.context`, phase field routing, and explicit prompt caching).
- [ ] Zero Completion Insurance & Prompt Caching:
  - Automatic zero-token billing protection and retry handler;
  - Dynamic prompt cache block optimization (`cache_control`) across large workspace context turns.
- [ ] Automated Provider Key Health Probes & Rotation:
  - Periodic background verification of upstream provider keys (OpenRouter, Groq, DeepSeek, Google AI Studio) with auto-quarantine for revoked credentials;
  - Automatic key rotation integration with Infisical and OpenRouter Management API Keys.
- [ ] Adaptive Fallback & Cost-Optimized Routing: latency and token cost aware routing across tier variants (Luna/Terra/Sol) with fallback to ultra-fast Groq endpoints on upstream 503/429.

### R8.2 — OpenRouter Agent SDK, Server Tools & Broadcast Observability

- [ ] OpenRouter Server-Side Tools Gateway:
  - Hosted Web Search (`web_search`) and Web Fetch (`web_fetch`) for live web grounding;
  - Hosted Sandboxed Shell (`shell`) and Apply Patch (`apply_patch`) for V4A diff file mutations;
  - Advisor Tool (`advisor`) for mid-generation token-efficient verification by stronger models;
  - Subagent Tool (`subagent`) for delegating bounded tasks to lightweight worker models;
  - Hosted Datetime (`datetime`) and Model Catalog Search (`search_models`).
- [ ] Agent Loop Hardening & Reliability Patterns:
  - Human-in-the-Loop (HITL) tool approval gates with resumable conversation state persistence;
  - Long-Horizon Agent loops with cost ceilings, token bounds, and voice/PTT interaction;
  - [x] Automatic Doom-Loop Detection: identify and abort repetitive tool calls, server-tool loops, or cyclical text without progress;
  - Dynamic parameter injection (`nextTurnParams`) for context-aware skills and modular plugin execution;
  - Typed Lifecycle Hooks (`beforeTurn`, `afterTurn`, `onToolCall`, `onToolResult`) for fine-grained execution governance.
- [ ] Multimodal Video & Media Synthesis Engine:
  - Dedicated Video Generation API: Text-to-Video, Image-to-Video (first/last frame control), and Reference-to-Video (style/subject guidance);
  - Asynchronous video webhook delivery with cryptographic signature verification;
  - Preset-Enhanced Image Generation pairing LLM prompt refinement with image generation server tools.
- [ ] Enterprise Observability & OpenTelemetry Broadcast:
  - OpenRouter Broadcast integration forwarding full generation traces directly to OpenTelemetry Collector, Langfuse, Grafana Cloud, Arize AX, Datadog, Comet Opik, Braintrust, and S3 sinks;
  - Analytics API integration for programmatic cost breakdown, token velocity, and activity exports.
- [x] Social Media & Provider Shop Connectors:
  - Social Media Connectors: Facebook Pages, Instagram Graph, TikTok Content/Creator, YouTube Data API, X (Twitter) v2, and LinkedIn Marketing;
  - E-Commerce / Provider Shop Connectors: Shopee Open Platform v2, TikTok Shop Seller API, and Facebook Commerce / Catalog Manager;
  - Platform HMAC signature verifiers (Shopee partner key, TikTok Shop sign, Meta AppSecret Proof);
  - Fail-closed approval governance for all mutating post publishing, inventory syncing, and pricing adjustments.
- [ ] Security Guardrails & Sovereign AI Compliance:
  - Regex and heuristic Prompt Injection detection with customizable phrase allowlists;
  - Sensitive Info Guardrails (automated PII masking/redaction before model egress);
  - Sovereign AI regional routing enforcement to maintain national/jurisdictional boundaries.

### R9 — Observability and SLO hardening

- [x] Voice session setup, STT, reasoning, TTS and end-to-end latency histograms.
- [x] PTT start failures, microphone denial, ticket rejection, reconnects and interruption counters.
- [x] Agent/skill invocation traces with redacted parameters and correlation IDs.
- [x] Continuous-agent heartbeat, stale-run and rate-limit metrics.
- [x] Dashboard health view for the complete speech/agent pipeline.

Target interactive SLOs remain engineering targets until measured in an authorized production-equivalent environment:

- session ticket p95 < 100 ms on local network;
- end-of-turn detection ~300–600 ms;
- first partial transcript < 700 ms where supported;
- first synthesized audio < 1.5 s on suitable hardware.

### R10 — Production release gate

Repository/CI evidence and external production evidence are distinct. Completion of repository checks does not imply the following external gates have passed.

- [x] Repository Python, Node, voice, contract, static asset and Windows validation surfaces are defined and covered by CI/release tooling.
- [x] Security review requirements for microphone, WebSocket, auth, CSP, secrets and approval boundaries are defined.
- [x] Dependency/SBOM/provenance gates are represented in repository workflows.
- [ ] Record authorized staging voice latency, failure recovery and provider failover evidence for the exact release candidate.
- [x] Accessibility verification coverage for keyboard, screen reader and reduced-motion modes is implemented in the repository surface.
- [x] Rollback target and feature flags are documented.

### R11 — Workspace Agent UX and local execution

This roadmap line translates the strongest public Skywork workspace-agent patterns into zWorkforce-native capabilities. Full sequencing and acceptance criteria are in `planning/exec-planning-skywork.md`.

- [x] Durable projects, conversations, search, pin/archive and stable conversation IDs foundation.
- [ ] Auto naming and richer history navigation UX.
- [ ] Context gauge, explicit `/compact`, question anchors and context snapshot history.
- [x] Slash command registry: `/plan`, `/review`, `/compact`, `/undo`, `/goal`, `/status`, `/artifacts`, `/cost`, `/skill`, `/workflow`, `/feedback` with UI autocomplete and server-side resolution.
- [x] Task summary sidecar with artifact manifest, review state, tool timeline and sanitized subagent hierarchy.
- [x] Operator-granted local workspace roots with path/symlink escape protection and bounded subprocesses.
- [x] Git branch/worktree adapter for isolated coding tasks; protected/default branches never mutated directly.
- [ ] Zider browser-use tool classes with read-only default and approval-gated side effects.
- [ ] Signed skill marketplace install, discovery scoring and repeated-workflow → draft skill/workflow candidate compiler.
- [ ] Markdown source/rendered preview, safe HTML preview and artifact history resilient across restarts.
- [ ] Task quick-start templates and evidence-based next-step suggestions.
- [ ] Theme profiles across web/WinUI without weakening accessibility/high-contrast support.
- [ ] FinOps preflight before expensive runs plus project/task/agent/model usage drilldown.
- [ ] Optional internal request signing with replay protection and key rotation for selected service-to-service boundaries.

### R12 — Agent Client Protocol (ACP) & OpenCode Architecture (Free Model First)

Adopt the architectural patterns from OpenCode-Book (`0xtresser/OpenCode-Book`):

- [x] **Agent Client Protocol (ACP) Server Endpoint**:
  - Implement bidirectional ACP JSON-RPC standard (`@agentclientprotocol/sdk`) over stdio and HTTP/SSE on zWorkforce API (`POST /acp`);
  - Standardized operations: `initialize`, `authenticate`, `newSession`, `loadSession`, `prompt`, `cancel`, `sessionUpdate` (text chunks, tool calls, tool progress), and `requestPermission` (HITL confirmation);
  - Direct integration support for IDEs (VS Code, Zed, Cursor) and native WinUI desktop companion.
- [x] **Comprehensive Model Metadata & Capability Matrix**:
  - Unified `ModelMetadata` schema tracking `capabilities` (`toolcall`, `reasoning`, `temperature`, `interleaved` reasoning fields), `cost` (input, output, prompt cache read/write), and `limit` (context window, max output);
  - Dynamic capability matching for **Free Model First** routing (e.g. verifying `toolcall: true` and `input.image: true` before dispatching to free models).
- [x] **Snapshot, Versioning & Undo Engine**:
  - Pre-mutation workspace file snapshots with checksum verification;
  - Granular undo/rollback capabilities for agent file changes (`/undo` command);
  - Visual diff calculation and state restoration.
- [x] **`oh-my-opencode` Specialist Agent Personas & Multi-Agent Collaboration**:
  - Specialist persona presets: `CodeReviewer`, `TestArchitect`, `SecurityAuditor`, `TechLead`, and `DocSpecialist`;
  - Standardized multi-agent handoffs with bounded context and explicit stop conditions;
  - All specialist agent runs default to OpenRouter Free Models (`openrouter/free`, `qwen-2.5-coder-32b:free`, `deepseek-r1:free`).

### R13 — Global AI Ecosystem Cookbooks & Safety Lifecycle Integration (Free Model First)

Adopt proven engineering patterns from official Anthropic, OpenAI, Google Gemini, Meta Llama, Groq, Mistral, HuggingFace, Liquid AI, Solana, Cursor, and community hook/skill repositories:

- [x] **Agent Lifecycle Hooks & Deterministic Safety Guards** (`yurukusa/claude-code-hooks`, `wasabeef/claude-code-cookbook`):
  - Pre-tool / post-tool execution hooks with deterministic safety gate filters;
  - `branch-guard`: block mutating execution on protected branches (`main`, `master`, `release/*`);
  - `secret-guard` & `destructive-guard`: pre-execution AST scan preventing command injection, `rm -rf`, or plaintext credential egress;
  - `auto-approve-readonly`: zero-friction auto-approval for read-only tools (`grep`, `glob`, `view_file`, `cat`) while keeping mutations approval-gated.
- [x] **Structured LLM Wiki & Pre-Mortem Prompting Patterns** (`gamer80hdd/claude-helpers`, `neklyudovs/claude-skills`):
  - Pre-mortem architectural analysis templates before generating multi-step execution plans;
  - LLM wiki pattern for compounding codebase knowledge without context window exhaustion;
  - Anti-AI-writing filters and tone calibrators for enterprise content production.
- [x] **Groq Ultra-Fast Inference & Reasoning Routing** (`groq/groq-api-cookbook`):
  - Prioritize Groq Free Tier quotas (`llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `deepseek-r1-distill-llama-70b`) for low-latency (<500ms TTFT) subagent steps;
  - Compound tool calling with JSON mode schema validation and structured output guarantees.
- [x] **Liquid AI Foundational Models (LFM) Edge Support** (`Liquid4All/cookbook`):
  - Support hybrid edge runtime for compact LFM-1B/3B and LFM-Vision on resource-constrained worker nodes;
  - Low-latency local audio transcription and vision triage without cloud egress.
- [x] **Multimodal Vision & Function Calling Standardization** (`google-gemini/cookbook`, `openai/openai-cookbook`, `anthropics/claude-cookbooks`, `meta-llama/llama-cookbook`):
  - Unified multimodal payload formatting (base64 image, audio chunks, PDF documents);
  - Dynamic tool schema generation with strict typed output parsing;
  - Context caching alignment across Gemini (`cachedContent`), Claude (`cache_control`), and OpenRouter Free Models.
- [x] **Decentralized Solana & Web3 Verification Infrastructure** (`solana-developers/solana-cookbook`):
  - Content provenance notarization and hash anchoring on Solana devnet/mainnet for tamper-proof audit trails;
  - Cryptographic keypair signature verification for agent-to-agent task attestation.

---

## 6. Monorepo Sub-Package Forward Roadmaps

### 6.1 ZSP AI Studio & Video Renderer (`packages/zsp-aitool`)
- **Mission**: Thai-First Shopee Affiliate Marketing Platform and HyperFrames multi-scene video rendering engine (`:3005` / `studio.zeaz.dev`).
- **Milestones**:
  - [x] Integrate the package data model with strict tenant isolation requirements.
  - [x] App Router app shell (`AppLayout`, `Sidebar`, `Header`, `MobileNav`).
  - [x] Admin & Operator audit panel gated behind `ADMIN_PANEL_ENABLED`.
  - [x] Shopee API product ingestion and OCR vision pipeline foundation.
  - [x] Multi-platform social publishing adapter surfaces.
  - [x] Video rendering watchdog with stale-job recovery.
  - [ ] OpenRouter Multimodal Video Generation Engine:
    - Text-to-Video and Image-to-Video generation (first and last frame conditioning);
    - Reference-to-Video styling and product identity consistency;
    - Asynchronous video webhook receiver with HMAC signature verification;
    - Preset-Enhanced image & thumbnail prompt compiler pairing with image generation server tools.

### 6.2 Zider AI Browser Companion (`packages/zider`)
- **Mission**: Manifest V3 AI Browser Sidebar Companion with Shadow DOM isolation, ChatPDF document intelligence, and multi-model group streaming (`:8085`).
- **Milestones**:
  - [x] Shadow DOM isolated sidebar and selection toolbar.
  - [x] Service worker background orchestrator and Chrome runtime message bus.
  - [x] Multi-model router with configured fallback support.
  - [x] Group AI multi-model streaming compare.
  - [x] ChatPDF tenant-scoped vector indexing and citation highlights.
  - [x] YouTube transcript summarizer and multi-language translator surfaces.
  - [ ] OpenRouter Rerank & Multimodal Integration:
    - High-precision RAG pipeline combining OpenRouter embeddings with `/rerank` API to filter top document chunks;
    - Multimodal PDF and image input handling with server-side URL and base64 parsing;
    - Model-agnostic web grounding via `:online` router variant and OpenRouter web-search plugin.

### 6.3 Zeto AI Content Factory (`packages/zeto`)
- **Mission**: Enterprise AI content lifecycle engine executing `IDEATE → GENERATE → WRITE → APPROVE → SCHEDULE → PUBLISH → MONITOR → LEARN`.
- **Milestones**:
  - [x] ProMeta prompt compiler architecture.
  - [x] Tool registry and point-cloud canvas HUD foundation.
  - [x] Multi-tenant content scheduling outbox with integrity protection.
  - [x] Automated QA scorecard evaluation and self-correction loops.
  - [ ] Token-Efficient Review & Delegation Architecture:
    - Advisor Server Tool integration: lightweight executor runs standard drafting and invokes Advisor for compact uncertainty validation;
    - Subagent Server Tool delegation: orchestrator generates structured task DAG and delegates sub-tasks to cheap worker models;
    - Automated Non-Blocking Code & Copy Review using lifecycle hooks;
    - Dynamic prompt caching (`cache_control`) for long-form brand guides and product catalogs.

### 6.4 Autonomous Workspace & Deep Research Super Agents (`zworkforce` + `packages/zeto`)
- **Mission**: Skywork-inspired multimodal workspace intelligence capable of turning prompts into end-to-end research reports, slide specs, structured spreadsheets, and TTS-ready audio scripts while retaining source provenance and approval boundaries.
- **Architectural Paradigms**:
  - **A2A (Agent2Agent) Protocol Support**: interoperability for workforce agents to discover capabilities, exchange bounded context, and delegate sub-tasks across heterogeneous runtimes.
  - **Deep Research Autonomous Engine**: iterative multi-hop search with OpenRouter `:online` web grounding, citation cross-referencing, document verification, and synthesis pipeline with source provenance.
  - **Multi-Model Deliberation (Fusion)**: combine insights from diverse LLM families to reach consensus on complex analytical findings.
  - **Cross-Model Memory Import**: standardized memory import/export with tenant, consent, and provenance controls.
  - **Multimodal Document Output Formats**: compilation of verified research into formatted Markdown, presentation specs, CSV/Excel data sheets, and TTS-ready audio scripts.

---

## 7. Non-goals

- Do not embed `apps/zvoice` with an iframe; its defensive framing policy is intentional.
- Do not send provider or service credentials to the dashboard or client extensions.
- Do not replace durable zWorkforce scheduler/approval/audit systems with a parallel OpenJarvis runtime.
- Do not claim a provider, model or external service is production-ready until operator evidence exists.
- Do not grant continuous agents unrestricted shell/network/action access.
- Do not grant a newly installed or auto-updated skill capabilities outside its existing authorized envelope.
- Do not treat local workspace access as permission to read or write arbitrary host filesystem paths.

## 8. Completion definition

The combined Z.A.R.V.I.S./workspace-agent upgrade is feature-complete when the control plane, Z.A.R.V.I.S. voice gateway, ZSP studio, Zider companion, and Zeto factory share unified tenant and secret boundaries, skills and agent modes are policy-governed and rollback-capable, scheduled/continuous operation has health and recovery controls, projects/conversations/context/artifacts are durable and tenant scoped, local/browser execution is sandboxed and approval-safe, FinOps is visible before and after execution, and all mutation continues through explicit approval/action boundaries.


## 5.1 Universal Local Stack Intelligence

The incremental ecosystem registry is maintained in docs/UNIVERSAL-STACK-INTELLIGENCE.md and its execution plan in planning/exec-planning-universal-stack.md.

Current evaluation candidates:

- fast-agent — P1 execution-runtime bake-off for local/Docker coding, Skills, MCP and ACP.
- AgentTeams — P1 orchestration adapter evaluation; it must not replace zWorkforce durable state, policy, approvals or audit authority.
- Agent Reach — P1 research capability under WATCH status until real backend reliability and credential isolation are demonstrated.

The registry requires upstream evidence, exact version checks, security validation and rollback/removal criteria before promotion. Free/public model providers are evaluated by capability, quota, data policy and operational reliability rather than by the existence of a free tier alone.
