# ADR-004: Workspace Sandbox Boundary

## Status

Accepted

## Context

Generated projects, shell execution, and deployment operations must be bounded by explicit approval and resource limits. Unsandboxed execution from browser or app surfaces is a critical security risk.

## Decision

`services/workspace-runtime` owns:
- Generated project validation (path safety, secret-bearing file rejection)
- Shell execution requests (explicit approval grant required)
- Deployment execution requests (explicit approval grant required)

Shell/deploy capabilities remain explicit grants. No app or service may execute shell or deploy commands without presenting an approved grant to workspace-runtime.

Generated files must:
- Declare generator ownership (`file.owner === "generator"`)
- Use safe paths (no leading `/`, no `..`, no secret-bearing extensions like `.env`, `.pem`, `.key`, `terraform.tfvars`)
- Pass project_id validation

## Consequences

- Apps (zow, zaicoder) proxy shell/deploy requests to workspace-runtime with approval grants.
- Workspace-runtime rejects any request without `approval.state === "approved"` and matching grant.
- Path traversal and secret-bearing file generation are blocked at validation time.
- Audit trail is maintained via agent-orchestrator for agent-initiated workspace operations.
