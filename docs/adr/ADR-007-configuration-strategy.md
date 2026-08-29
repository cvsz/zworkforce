# ADR-007: Configuration Strategy

## Status

Accepted

## Context

Environment variables are scattered across `.env`, `.env.example`, `.env.zarvis.local`, `.env.zarvis.voice.local`, and `.env.zarvis.voice.local.bak`. Variables are inconsistently named, undocumented, and lack type validation. Production services fail at first request rather than startup when required config is missing.

## Decision

1. `.env.example` is the canonical template for local development.
2. `packages/config` provides typed configuration schemas per domain (platform, ai, agent, workspace, billing, voice, zarvis).
3. Runtime startup validates required configuration and fails closed with clear error messages.
4. Production-sensitive configuration (secrets, tokens, keys) must be provided via environment or secret manager; no defaults are permitted.
5. Duplicate or obsolete variables are removed from `.env.example`.
6. Variable naming follows `<DOMAIN>_<PURPOSE>` pattern (e.g., `AI_GATEWAY_CORS_ORIGIN`, not `CORS_ORIGIN`).

## Consequences

- Local onboarding is reproducible (`cp .env.example .env && make dev`).
- CI catches misconfiguration before deployment.
- Security reviews can verify that no browser-accessible code references server-only variables.
- Operator runbooks reference a single canonical variable list.
