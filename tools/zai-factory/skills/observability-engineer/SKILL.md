---
name: observability-engineer
description: Define production observability for Z Platform services.
source:
  repository: cvsz/zeaz-platform
  path: apps/zai-factory/skills-vault/skills/observability-engineer/SKILL.md
---

# Observability Engineering

Apply this skill to every deployable Z Platform service.

## Required signals

- Structured JSON logs with request ID, tenant ID when authorized, service name, and severity.
- Metrics for request count, duration, failures, queue depth, retries, and upstream availability.
- Traces across browser proxy, AI gateway, agent jobs, and billing events.
- Health and readiness endpoints that do not expose secrets.

## Rules

1. Redact credentials, prompts containing secrets, payment data, wallet material, and provider headers.
2. Do not use tenant identifiers as high-cardinality metric labels.
3. Propagate a correlation ID across API, event, and audit boundaries.
4. Define dashboards and alerts before enabling a production workload.
5. Test failed upstream, timeout, retry, and cancellation paths.

## Delivery gate

A service is not production-ready until its logs, metrics, traces, health endpoints, and rollback signal are documented.
