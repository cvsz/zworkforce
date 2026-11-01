# ZAI Coder Web

This package is the browser-facing ZAI Coder shell. It must route all AI requests through the platform AI Gateway and must never expose upstream provider credentials to browser code.

## Runtime

- Static browser assets are served from the public directory.
- Tenant-scoped API routes are intentionally fail-closed with HTTP 503 and Cache-Control: no-store until a trusted authentication and tenant-membership boundary is implemented.
- The disabled routes are POST /api/chat, POST /api/chat/stream, POST /api/files, POST /api/workspaces, and GET /api/workspaces/:id.
- Caller-supplied X-Tenant-Id headers, request-body owner fields, workspace IDs, and roles are not identity proof and are not accepted as authorization.
- The HTTP server can be imported through createZaiCoderServer for isolated integration tests; importing the module does not start a listener.

## Required environment for a future authenticated runtime

The following settings are not sufficient to enable the API by themselves. They must only be consumed after a trusted identity boundary has been implemented and verified.

- Z_PLATFORM_AI_GATEWAY_URL: AI Gateway base URL. Both http://gateway:8400 and http://gateway:8400/v1 are accepted.
- Z_PLATFORM_SERVICE_TOKEN: server-side service token. It must never be exposed to browser code.
- ZAICODER_WORKSPACE_ADAPTER optional, defaults to file. Set to http for the production durable metadata adapter.
- ZAICODER_WORKSPACE_STORE optional, defaults to .zaicoder-workspaces for the file-backed adapter.
- ZAICODER_WORKSPACE_METADATA_URL required when ZAICODER_WORKSPACE_ADAPTER=http.
- ZAICODER_WORKSPACE_METADATA_TIMEOUT_MS optional, defaults to 5000.
- HOST optional, defaults to 127.0.0.1.
- PORT optional, defaults to 3005.

## Tenant identity admission requirements

Do not re-enable any tenant-scoped API route until all of the following are implemented and tested:

1. Validate a server-trusted OIDC/JWKS identity, including issuer, audience, signature, expiry, and key rotation.
2. Resolve the authenticated subject to an active tenant membership and current RBAC record using authoritative server-side data.
3. Derive tenant identity exclusively from the verified principal. Never use X-Tenant-Id, body owner, tenant_id, role, or plan as authority.
4. Propagate the verified tenant context through workspace persistence, file ownership, AI Gateway usage attribution, audit records, and downstream service authorization.
5. Prove positive and negative cross-tenant cases with real HTTP integration tests, including forged headers, missing identity, revoked membership, and workspace/file ID substitution.
6. Keep the API unavailable until the exact-head CI, security checks, independent review, and production identity/secret provisioning evidence pass.

## Workspace metadata

The WorkspaceStore adapter supports file-backed local metadata and an HTTP metadata service. It validates workspace IDs, records owner, enforces owner matches when an owner is supplied by trusted server code, clamps retention to a maximum of 365 days, stores timestamps, tracks uploaded file references, and exposes explicit retention cleanup.

The storage-layer owner comparison does not authenticate an HTTP caller. The current HTTP API therefore remains disabled. Do not treat a caller-supplied tenant header as trusted identity.

Run npm run cleanup:workspaces from this package only as an explicitly configured operator maintenance job. The runner uses the configured adapter and emits a structured JSON event with removed_count and removed workspace IDs.

## Validation

Run npm test in this directory to check gateway request validation, streaming forwarding, file upload forwarding, workspace metadata persistence, retention validation, tenant owner enforcement, durable adapter behavior, cleanup behavior, and the tenant-auth-boundary HTTP tests.
