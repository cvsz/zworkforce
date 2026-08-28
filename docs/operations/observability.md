# Observability and Health

## Health endpoints

| Service | Endpoint | Notes |
|---|---|---|
| AI Gateway | `GET /health` | Reports upstream configuration only, never secrets |
| ZAI Coder Web | package tests | Gateway-only proxy boundary |
| ZChat | `GET /health` | Reports gateway/session configuration |
| Agent Orchestrator | `GET /health` | Reports execution mode and external traffic gate |
| Workspace Runtime | `GET /health` | Reports approval-gated sandbox boundary |
| Billing Ledger | `GET /health` | Confirms no wallet/card authority |
| ZWallet Adapter | `GET /health` | Confirms billing adapter only |

## Structured logs

Every service must log JSON with:

- `ts`
- `service`
- `event`
- `request_id`
- `tenant_id` when available
- `status`
- redacted error code

## Metrics

Minimum metrics before production:

- request count by service/path/status
- latency histogram by service/path
- upstream failure count
- usage records accepted/duplicate/rejected
- agent job terminal state count
- approval-denied count

## Traces

Propagate `X-Request-Id`, conversation IDs, usage-correlation IDs, and tenant IDs across internal service calls. Do not include provider credentials, card data, wallet signatures, KYC payloads, MPC shares, or raw prompts in trace attributes.
