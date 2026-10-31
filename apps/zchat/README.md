# ZChat

ZChat is the platform chat surface migrated from the canonical platform application. Browser code must never contain upstream provider keys, direct provider base URLs, or tenant-wide service credentials.

## Runtime

- GET /health and GET /health/live return minimal liveness metadata only; they do not expose gateway configuration or internal backend status.
- GET / serves the static accessible chat shell.
- POST /api/logout clears browser storage through Clear-Site-Data.
- GET /api/models, GET /api/platform/status, POST /api/chat, and POST /api/chat/stream intentionally return HTTP 503 with Cache-Control: no-store until trusted authentication and tenant membership are implemented at this HTTP boundary.
- Caller-supplied X-Tenant-Id and X-Session-Started-At headers are not proof of identity, tenant membership, or session validity.
- The exported chat/model helper functions are not exposed by the HTTP routes while identity admission is unavailable.

## Required environment for a future authenticated runtime

These settings do not enable API access by themselves. Do not expose them to browser code.

- Z_PLATFORM_AI_GATEWAY_URL: AI Gateway base URL.
- Z_PLATFORM_SERVICE_TOKEN: server-side service credential for the AI Gateway.
- PHASE6_API_URL and ZC_API_URL: internal backend URLs used by the platform status facade.
- PHASE6_API_TOKEN and ZC_API_TOKEN: optional server-side backend credentials.
- ZCHAT_SESSION_TTL_SECONDS: a future server-validated session policy setting. A caller-supplied start timestamp is not an authentication control.
- HOST optional, defaults to 127.0.0.1.
- PORT optional, defaults to 3021.

## Tenant identity admission requirements

Do not re-enable model catalog, platform status, chat, or streaming routes until all of the following are implemented and tested:

1. Validate a server-trusted OIDC/JWKS identity, including issuer, audience, signature, expiry, and key rotation.
2. Resolve the authenticated subject to an active tenant membership and current RBAC record using authoritative server-side data.
3. Derive tenant identity exclusively from the verified principal. Never use X-Tenant-Id, X-Session-Started-At, body tenant_id, role, or plan as authority.
4. Propagate verified tenant context through AI Gateway usage attribution, conversation storage, rate limits, audit records, and downstream authorization.
5. Prove positive and negative cross-tenant cases with real HTTP integration tests, including forged headers, missing identity, expired/revoked membership, and conversation ID substitution.
6. Keep the routes unavailable until exact-head CI, security checks, independent review, and production identity/secret provisioning evidence pass.

## Validation

Run npm test in this directory to check direct gateway helper contracts, session handling, cancellation, static browser behavior, logout, public health redaction, and the fail-closed HTTP tenant boundary.

## Migration limits

The UI remains a platform-owned chat client. Production deployment still requires the selected platform identity/session provider and end-to-end accessibility/mobile QA in the deployed environment.
