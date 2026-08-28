# Workspace Runtime

The workspace runtime is the isolated execution boundary for generated projects and workspace actions.

It validates generated-file ownership and blocks shell or deployment actions unless an explicit approval object grants the requested action.

## Runtime

- `GET /health` reports service status.
- `POST /v1/projects/validate` validates project IDs and generated file ownership.
- `POST /v1/shell` accepts shell execution requests only with `approval.state=approved` and a `shell` grant.
- `POST /v1/deploy` accepts deployment requests only with `approval.state=approved` and a `deploy` grant.

All non-health endpoints require `Authorization: Bearer <Z_PLATFORM_SERVICE_TOKEN>`.

## Validation

Run `npm test` to check safe generated files, secret-bearing file rejection, service-token authorization, and approval-gated shell/deploy requests.
