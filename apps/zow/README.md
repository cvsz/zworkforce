# ZOW Workspace

ZOW is the user-facing workspace layer for Z Platform.

The execution runtime is deliberately separate in `services/workspace-runtime`. ZOW forwards validation, shell, and deployment requests to that runtime; it does not execute shell commands or create deployments locally.

## Runtime

- `GET /health` reports whether the workspace runtime is configured.
- `POST /api/projects/validate` forwards generated project validation requests.
- `POST /api/shell` forwards approval-gated shell requests.
- `POST /api/deploy` forwards approval-gated deployment requests.

## Required environment

- `Z_PLATFORM_WORKSPACE_RUNTIME_URL`: workspace runtime service URL.
- `Z_PLATFORM_SERVICE_TOKEN`: server-side service token for runtime calls.
- `HOST` optional, defaults to `127.0.0.1`.
- `PORT` optional, defaults to `3030`.

## Validation

Run `npm test` to verify ZOW stays a UI/proxy boundary and does not bypass runtime approval.
