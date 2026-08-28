# ZAI Coder Web

This package is the browser-facing ZAI Coder shell. It must route all AI requests through the platform AI Gateway and must never expose upstream provider credentials to browser code.

## Runtime

- `POST /api/chat` forwards non-streaming chat requests to the AI Gateway.
- `POST /api/chat/stream` forwards streaming chat requests and returns server-sent events.
- `POST /api/files` forwards file uploads to the AI Gateway. When `X-Workspace-Id` is present, the uploaded platform file reference is linked into that workspace metadata record.
- `POST /api/workspaces` creates or updates workspace metadata with `workspace_id`, `owner`, and `retention_days`.
- `GET /api/workspaces/:id` returns the stored workspace metadata or `404` when it does not exist.
- Static browser assets are served from `public/`.

## Required environment

- `Z_PLATFORM_AI_GATEWAY_URL`: AI Gateway base URL. Both `http://gateway:8400` and `http://gateway:8400/v1` are accepted.
- `Z_PLATFORM_SERVICE_TOKEN`: service token used only by the server-side proxy.
- `ZAICODER_WORKSPACE_ADAPTER` optional, defaults to `file`. Set to `http` for the production durable metadata adapter.
- `ZAICODER_WORKSPACE_STORE` optional, defaults to `.zaicoder-workspaces` for the file-backed adapter.
- `ZAICODER_WORKSPACE_METADATA_URL` required when `ZAICODER_WORKSPACE_ADAPTER=http`; points to the server-side workspace metadata service backed by the selected database/object store.
- `ZAICODER_WORKSPACE_METADATA_TIMEOUT_MS` optional, defaults to `5000`.
- `Z_PLATFORM_SERVICE_TOKEN` is also used by the HTTP workspace adapter as a server-side bearer token.
- `HOST` optional, defaults to `127.0.0.1`.
- `PORT` optional, defaults to `3010`.

## Workspace metadata

Workspace metadata is accessed through a `WorkspaceStore` adapter boundary. The default adapter is file-backed JSON for local development. Production deployments should set `ZAICODER_WORKSPACE_ADAPTER=http` and point `ZAICODER_WORKSPACE_METADATA_URL` at the platform metadata service backed by the selected database/object store.

The store validates workspace IDs, records an owner field, enforces owner matches when `X-Tenant-Id` is supplied, clamps retention to a maximum of 365 days, stores `created_at`, `updated_at`, and `expires_at`, tracks uploaded file references with `added_at` timestamps, and exposes explicit retention cleanup.

Run `npm run cleanup:workspaces` from this package in a cron job or one-shot container to remove expired workspace metadata. The runner uses the configured adapter and emits a structured JSON event with `removed_count` and removed workspace IDs.

Example create/update request:

```json
{
  "workspace_id": "demo-workspace",
  "owner": "tenant-1",
  "retention_days": 30
}
```

In platform deployments, send `X-Tenant-Id` on workspace read/write and file-linking requests so metadata cannot be reused across tenant boundaries.

## Validation

Run `npm test` in this directory to check chat validation, gateway URL normalization, streaming forwarding, file upload forwarding, workspace metadata persistence, retention validation, tenant owner enforcement, durable adapter behavior, cleanup behavior, cleanup runner output, and invalid input handling.

## Current limits

File uploads currently return platform file references and can be linked to workspace metadata. Production deployments must run a workspace metadata service that exposes `GET /workspaces`, `GET /workspaces/:id`, `PUT /workspaces/:id`, and `DELETE /workspaces/:id` over HTTPS or private service networking and persists records in the approved database/object store.
