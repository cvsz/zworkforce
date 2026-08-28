# ZeaZ Provider 0.4.0 Production Readiness Audit

Date: 2026-08-02

## Scope and source decision

The requested `zeaz-provider-0_4_0rc1-patched.zip` was not present in the
available filesystem. The existing `/home/cvsz/z-prov` checkout was already a
clean Git repository, so it was preserved and audited in place rather than
overwritten by an unverified archive.

The audit covered all 61 production Python files under `src/` and
`packages/*/src/`, 58 test files, container and Compose definitions, installer
scripts, dependency-lock enforcement, release metadata, and documentation.

## Implemented hardening

- Routed streaming requests through total-deadline, retry, and circuit-breaker
  logic while preventing retries after the first emitted byte.
- Restored circuit state safely after cancellation, process cancellation, and
  half-open probe cleanup.
- Made protocol conversion fail closed for invalid tool JSON, unsupported
  content/tool types, malformed tool names or IDs, nonstandard JSON constants,
  and invalid provider responses.
- Added CR/LF-safe SSE framing and sanitized native upstream error events.
- Added function-call event translation for Chat-to-Responses and corrected
  output/content index collisions across streaming protocols.
- Made stale batch idempotency reservation reclamation atomic and reject
  concurrent claims instead of duplicating external operations.
- Added cancellation-safe subprocess/container reader cleanup and strict
  sandbox workspace delimiters.
- Revalidated existing signed plugin content and canonical install paths on
  reinstall.
- Hardened service URL origins, ports, provider credentials, control-plane
  JSONL, and provider response parsing.
- Promoted the gateway release metadata to stable `0.4.0`; SBOM generation now
  reads the project version instead of duplicating it.

## Required validation

Run these commands from the repository root before publishing an artifact:

```bash
make validate
docker compose config --quiet
make validate-container
```

Also run the restricted-key provider contract suite, a no-cache image build,
SBOM and vulnerability scans, signed update-manifest verification, and the
fresh Ubuntu/VMware acceptance flow. These require external infrastructure or
credentials and are not simulated by unit tests.

## Release gates not claimed by this audit

- Live provider contract tests for every configured Anthropic/OpenAI-compatible
  integration.
- Docker daemon runtime validation in the current execution environment.
- Signed release archive, detached manifest signature, provenance, and external
  vulnerability scan publication.
- Fresh Ubuntu 26.04 VMware install/upgrade, backup restore, and disaster
  recovery exercise.
- Terraform, Cloudflare, TLS, WAF, secret-manager, and incident-response
  deployment validation.
- Public web-console exposure: the web profile remains loopback-bound and
  requires an authenticated reverse proxy or Cloudflare Access before remote
  use. Normal dashboard APIs do not provide standalone end-user auth.
- Optional `zeaz-agent`, `zeaz-sandbox`, `zeaz-control`, `zeaz-enterprise`,
  `zeaz-web`, and `zeaz-infra` distributions remain separately versioned
  prerelease packages; this audit does not silently promote them to `1.0`.

The gateway code is suitable for a controlled `0.4.0` release after the
external gates above are completed. This document intentionally does not call
the entire platform a blanket v1.0 production sign-off.
