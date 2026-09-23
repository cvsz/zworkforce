# Universal Local Stack Intelligence

Status: active forward integration registry
Repository: cvsz/zworkforce
Review date: 2026-09-20
Decision mode: Free/Open Source + local-first + self-hosted first

This document records verified ecosystem deltas that are candidates for the zWorkforce Universal Local Stack. A project is not promoted to a production dependency merely because it is popular or feature-rich.

## Decision rules

- Verify license, cost, self-hosting, OS/container/CLI compatibility, MCP/ACP integration, sandboxing, secret handling, maturity and migration effort.
- Preserve zWorkforce as the authority for tenant policy, approvals, durable state, provider access, secrets and audit.
- Do not infer production readiness, quotas, external infrastructure or security properties from an adapter alone.

## 2026-09-20 verified deltas

### 1. fast-agent — EVALUATE / P1

Upstream: https://github.com/evalstate/fast-agent  
License: Apache-2.0.  
Role: coding-agent/runtime, Skills, MCP and ACP execution candidate.

Upstream documents CLI-first workflows, Agent Skills, MCP, ACP, shell execution, local model/provider support and isolated execution environments. The 0.9 line introduced named local, Docker, Hugging Face Sandbox and custom execution environments; the v0.9.20 release also contains environment, monitoring and process-related fixes.

Decision: evaluate in an isolated execution bake-off; do not make it a privileged default runner.

Security: use bounded workspaces, avoid exposing Docker socket, restrict network egress and keep provider credentials outside agent-visible workspaces.

Acceptance: read-only task, bounded write task, host-path escape test, MCP scope test, timeout/cancel test and trace/cost evidence.

### 2. AgentTeams — EVALUATE / P1

Upstream: https://github.com/agentscope-ai/AgentTeams  
Role: Kubernetes-native multi-agent coordination with Matrix human-in-the-loop workflows.

The upstream project has moved from the v1.2.0-beta contract to stable v1.2.x. The v1.2 line finalized AgentTeams naming/resource contracts, moved Team membership to standalone Worker references, added an optional Dashboard and improved installer/tooling safety. Earlier beta work added plugin, TeamHarness, WorkerFlow, MCP, model-provider preflight and controller observability capabilities.

Decision: evaluate as a separate orchestration adapter; do not replace zWorkforce durable state, approval, policy, audit or provider authority.

Security: review CRD/Helm changes, Matrix identity/SSO, provider authorization, worker resource limits and network access before promotion.

Acceptance: local-only deployment, Worker/Team lifecycle, least-privilege MCP, human approval, restart/reconcile, metrics/traces and rollback rehearsal.

### 3. Agent Reach — WATCH / P1

Upstream: https://github.com/Panniantong/Agent-Reach  
License: MIT.  
Role: web/research ingestion and multi-backend public platform access.

v1.5.0 introduced ordered per-platform backends, diagnostics and OpenCLI-oriented routing. This can reduce the need for a paid API for every research source.

Decision: WATCH/EVALUATE only. Upstream/community reports document platform drift, login-state dependencies, Windows-specific issues and credential-write/security concerns around the v1.5.0 generation.

Security: isolate research workers, use source allowlists and rate limits, capture provenance, and never place browser credentials/cookies into general agent context.

Acceptance: compare diagnostics with real commands, verify each enabled backend end-to-end, record source/time/collector version and test fallback behavior.

## Free API / provider policy

Do not add a provider to the production baseline solely because it advertises a free tier.

For each provider record the official endpoint, authentication, exact quota/limits, model availability, data policy, tool-calling support, rate limits, regional restrictions and fallback behavior.

Preferred order: local model; self-hosted OpenAI-compatible endpoint; verified free/public endpoint; paid provider only when required capability is unavailable locally.

## Universal stack placement

zWorkforce control plane -> policy/approval/audit/durable state -> agent router -> coding runtime / research runtime / distributed orchestration -> MCP/tool gateway -> local model gateway.

## Current decisions

| Component | Decision | Next action |
| --- | --- | --- |
| fast-agent | EVALUATE / P1 | execution bake-off |
| AgentTeams | EVALUATE / P1 | orchestration adapter spike |
| Agent Reach | WATCH / P1 | isolated research-worker validation |
| New paid provider | NO ADD | require verified capability gap |

## Evidence policy

Every future entry must include upstream release/docs evidence and, where relevant, an explicit note when community reports qualify upstream claims. Never copy an upstream popularity ranking into a zWorkforce decision.
