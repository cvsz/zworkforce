# ADR-002: Gateway-Only AI Access

## Status

Accepted

## Context

Upstream AI providers must not be called directly from browser applications or thin app proxies. Secrets, rate limits, quotas, audit trails, and provider failover must remain behind a single production boundary.

## Decision

`services/ai-gateway` is the sole production boundary for upstream AI provider access.

Responsibilities:
- Provider credentials (server-side key pools in Redis)
- Provider adapters (OpenAI-compatible, Anthropic Messages)
- Model catalog
- Request normalization
- Streaming (SSE passthrough)
- Upload/attachment translation (planned)
- Usage emission to billing
- Quotas and rate limiting
- Provider fallback (multi-provider chain)
- Request IDs and correlation
- Redacted telemetry

No browser application may contain upstream provider credentials or call upstream providers directly.

The only exception is `services/phase6-api`, which calls upstream providers for external staging verification. This exception is operator-approved and isolated to staging verification.

## Consequences

- Apps (zchat, zaicoder, zvoice) proxy all AI requests through ai-gateway.
- Provider keys never leave the ai-gateway runtime.
- Usage events flow from ai-gateway to billing-ledger.
- CI enforces browser credential isolation.
