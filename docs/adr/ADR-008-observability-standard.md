# ADR-008: Observability Standard

## Status

Accepted

## Context

Telemetry is inconsistent across services. Some use Pino, some use stdout JSON, some use Prometheus metrics, some use no structured logging. Correlation across service boundaries is manual and error-prone.

## Decision

Every deployed service emits structured logs with the following fields:

```json
{
  "timestamp": "ISO8601",
  "service": "service-name",
  "environment": "local|staging|production",
  "event": "event-name",
  "request_id": "uuid",
  "trace_id": "uuid (when available)",
  "tenant_id": "tenant identifier or anonymous",
  "actor_id": "user or service identifier",
  "status": "ok|degraded|error",
  "error_code": "machine-readable error code",
  "duration_ms": "request duration in milliseconds"
}
```

Rules:
- No sensitive payloads in logs (redact auth headers, API keys, tokens, PII).
- Trace correlation crosses service boundaries via `X-Request-Id` and `traceparent` headers.
- Metrics include: request rate, latency, failures, upstream provider failures, queue depth, job terminal states, retry counts, approval denials, sandbox failures, usage ledger states, billing idempotency failures.
- Health endpoints distinguish liveness (`/health/live` or `/healthz`) from readiness (`/ready`).

## Consequences

- Operators can trace requests across services using `request_id`.
- Alerting is based on consistent metric names.
- Security incidents can be investigated without exposing secrets in logs.
- New services have a clear observability template to follow.
