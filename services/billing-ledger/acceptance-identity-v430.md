# Candidate financial identity boundary — v430

This is a **candidate-only**, dependency-injected JWT-to-tenant resolver. It is not connected to any HTTP route or production identity provider. All financial HTTP mutation routes must continue to return 503 to authenticated callers. Do not infer production authorization from unit tests.

## Trust boundaries

- The caller supplies only a compact JWT as `principal.token`; decoded objects, request body `tenant_id`, and token `role` claims are not authorities.
- An operator configures an exact HTTPS `issuer`, exact `audience`, and a `getJwks()` function that fetches/caches public signing keys from the **pinned trusted issuer**. This module deliberately never follows `jku`, `x5u`, embedded `jwk`, or any token-provided URL.
- The verifier accepts only `RS256` JWTs with a unique `kid`, a minimum 2048-bit RSA public key, a short-lived token, and the `billing:write` scope. Key material is public-only; no private signing keys are required.
- The `lookupMembership({subject, tenantId})` function **must** query an authoritative server-side tenant membership store and return `{active: true, role: 'billing_writer'}` only after authorization. A JWT claim alone cannot grant membership.
- A missing or invalid token, key, claim, or membership is denied. Key-service and membership-service errors fail closed with 503. The adapter independently compares the verified tenant to the financial record's `tenant_id` before opening a database connection.
- The resolver and its dependencies must be instantiated on the server, not in a browser or by user-controlled configuration. Operator-controlled issuer key rotation, TLS, JWKS cache expiry, rate limits, membership revocation latency, audit correlation, and trusted production IdP integration are **not implemented** here.

## Verification

```bash
node --check services/billing-ledger/tenant-identity.mjs
node --test services/billing-ledger/test/tenant-identity-v430.test.mjs
node --test services/billing-ledger/test/*.test.mjs
```

Tests generate synthetic RSA keys in memory and never call external IdP, database, payment, or production services. The adapter boundary test uses a fake pool; no PostgreSQL E2E or production AuthN evidence is claimed. The existing PostgreSQL 17 workflow should execute the new tests via its in-process financial regression step.

## Production admission still blocked

1. Configure an operator-owned OIDC issuer and pinned JWKS source with bounded TLS fetch, cache and key-rotation behavior; verify discovery metadata independently.
2. Implement and independently audit the authoritative tenant-membership backend, revocation, scoped RBAC, multi-tenant membership semantics and audit logs.
3. Test real issuer tokens, revoked memberships, key rotation, unavailable IdP, tenant mismatches, concurrent sessions, rate limiting and negative end-to-end API cases in an isolated staging environment.
4. Complete exact-head CI, dependency review, independent security approval, signed release, durable database migration, backup/restore/PITR and operator GO decision.

Rollback: revert only the candidate module, tests and this document on the draft branch. Keep financial HTTP writes disabled. Never roll back to an unauthenticated tenant resolver or disable PostgreSQL RLS.
