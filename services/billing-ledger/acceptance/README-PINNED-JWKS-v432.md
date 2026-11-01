# Pinned OIDC JWKS Transport — v432 (candidate only)

This module provides an **operator-configured, same-origin HTTPS JWKS transport** for the existing `createFinancialTenantResolver({ getJwks })` dependency. It is **not** wired to any financial HTTP route, real identity provider, tenant-membership database, or production environment. Financial mutations remain disabled (503).

## Trust model

- Configure `issuer` and exact `jwksUrl` from an independently verified issuer configuration. Both must be HTTPS, have the same origin, and the JWKS URL must be under the issuer path. This restrictive policy may require a separately reviewed adapter for IdPs with cross-origin JWKS endpoints.
- No JWT `jku`, `x5u`, embedded `jwk`, tenant claim, request body, or user input may influence `jwksUrl`.
- Fetch uses TLS validation, no redirects, no credentials, an AbortSignal timeout, strict JSON content type, a 64 KiB default response cap, and a 30-second default cache TTL. The operator can reduce TTL for key revocation requirements; no stale-key fallback is allowed after expiration.
- Concurrent requests share a single refresh; callers receive isolated key objects. Clock rollback and invalid clock fail closed. This is public-key transport, **not** proof of key revocation, token revocation, membership authorization, or IdP availability.
- Do not expose operator configuration or `fetchFn` injection to untrusted callers. In production use the default Node.js `fetch`; `fetchFn` exists for deterministic isolated tests.

## Isolated verification

```bash
node --check services/billing-ledger/pinned-jwks.mjs
node --test services/billing-ledger/test/pinned-jwks-v432.test.mjs
node --test services/billing-ledger/test/*.test.mjs
```

Tests use an in-memory fetch stub; no external identity or customer network is contacted. A successful exact-head hosted CI run is required before considering the code verified in CI.

## Remaining admission gates

1. Independently verify production issuer metadata, HTTPS trust chain, approved JWKS URI, certificate rotation and external failure modes.
2. Implement authoritative tenant membership and revocation with bounded propagation latency; audit role changes and denied operations.
3. Run isolated end-to-end OIDC token issuance, key rotation, outage, cross-tenant authorization and PostgreSQL RLS tests.
4. Verify production rate limiting, audit correlation, SLOs, rollback, exact-head CI, independent review and operator GO.

Rollback this candidate module and its tests on the draft branch if needed; do not remove the financial HTTP containment, RLS or JWT signature verification.
