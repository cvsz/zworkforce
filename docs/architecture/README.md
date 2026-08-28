# Architecture

## Domain ownership

| Domain | Location | Responsibility |
|---|---|---|
| Product UI | `apps/*` | User-facing web, desktop, mobile interfaces, including ZOW workspace UI/proxy |
| AI gateway | `services/ai-gateway` | Provider routing, quotas, policy enforcement |
| Agent orchestration | `services/agent-orchestrator` | Task lifecycle, durable store/queue adapters, scoped tool policy, sandbox workers, and audit events |
| Workspace runtime | `services/workspace-runtime` | Approval-gated generated project validation, shell, and deployment boundaries |
| Research | `services/research-worker` | Isolated research jobs and report output |
| Billing | `services/billing-ledger` | Idempotent AI usage accounting, credits, limits, and invoice-intent boundary |
| Shared contracts | `packages/contracts` | Versioned API/event schemas |

## Trust boundaries

Clients never receive provider secrets. Agent workloads execute with least privilege and only after versioned approval events grant bounded tools. Workspace shell and deployment requests are isolated behind explicit approval grants. The billing ledger only receives validated usage events, credits, and invoice intents; it never receives wallet signing authority, card data, KYC payloads, MPC shares, or swap routes.
