# Z.A.R.V.I.S. Owner-Only Access Model

## Security objective

Only the owner of this private assistant may load the command center or invoke any tool.

The owner identity is permanently bound in source code to:

| Attribute | Value |
|---|---|
| GitHub login | `cvsz` |
| Immutable GitHub user ID | `4076926` |
| Audit user ID | `github:4076926` |
| Audit tenant ID | `owner-4076926` |

GitHub login names can change, so authorization is based on the numeric GitHub user ID. The implementation intentionally provides no environment variable, API, database field, invitation flow, role assignment, or administrative endpoint that can replace the owner.

## Enforcement chain

```text
Owner browser
    |
    | identity-provider login
    v
Trusted edge / Cloudflare Access + Worker
    | 1. verify the exact owner identity
    | 2. remove all incoming x-zarvis-* headers
    | 3. inject owner ID 4076926 and edge secret
    v
ZARVIS Console
    | 4. constant-time verify edge secret
    | 5. reject every route except /healthz on failure
    | 6. replace all caller identity headers
    v
ZARVIS Orchestrator
    | 7. verify owner ID and console service token
    | 8. derive audit identity only from source invariant
    v
Read-only tools
```

## Required secrets

Two independent high-entropy values are required:

- `ZARVIS_EDGE_SHARED_SECRET` authenticates the trusted edge to the console.
- `ZARVIS_ORCHESTRATOR_SERVICE_TOKEN` authenticates the console to the orchestrator.

Each secret must contain at least 32 random bytes. They must be generated independently, stored in the deployment secret manager, rotated independently, and never exposed to browser JavaScript, logs, Git, build artifacts, URLs, or analytics.

The service refuses to start when a required secret is absent or shorter than 32 bytes.

## Trusted edge requirements

The edge configuration must:

1. Allow only the owner's identity-provider account.
2. Validate the identity token before forwarding a request.
3. Strip user-supplied `x-zarvis-owner-id`, `x-zarvis-edge-secret`, and other `x-zarvis-*` headers.
4. Inject `x-zarvis-owner-id: 4076926` only after successful authentication.
5. Inject `x-zarvis-edge-secret` from an edge-side secret store.
6. Prevent the browser from reading or setting the secret.
7. Deny bypass paths to the origin.

Cloudflare Access or another identity-aware proxy is the expected external boundary. A Worker or equivalent trusted proxy should perform header removal and injection.

## Origin isolation

Header checks are defense in depth, not a replacement for network isolation.

- The console origin must accept public traffic only from the trusted edge network.
- The orchestrator must be private and reachable only from the console network identity.
- Do not publish the orchestrator port to the public internet.
- Use TLS for any connection crossing a host or trust boundary.
- Restrict health endpoints to infrastructure monitoring where possible.

## Request behavior

| Request | Result |
|---|---|
| `GET /healthz` | Allowed for infrastructure health checks |
| Console route without owner assertion | `403 owner_access_denied` |
| Console route with wrong owner ID | `403 owner_access_denied` |
| Console route with wrong edge secret | `403 owner_access_denied` |
| Direct orchestrator request | `403 owner_access_denied` |
| Orchestrator request with forged user/tenant headers | Headers ignored; owner identity is regenerated |
| Missing runtime secrets | Process startup fails |

Authentication failures use a generic response and do not reveal which credential was incorrect.

## Explicit non-goals

This system does not support:

- registration or account creation;
- guest access;
- shared accounts;
- organization members;
- invitations;
- delegated administrators;
- multiple tenants;
- owner reassignment;
- public API keys;
- anonymous command execution.

Adding any of these capabilities requires a new security review and a separate architecture decision. They must not be introduced as a compatibility shortcut.

## Rotation and emergency revocation

To revoke access immediately:

1. Disable the owner policy at the identity edge.
2. Rotate `ZARVIS_EDGE_SHARED_SECRET`.
3. Rotate `ZARVIS_ORCHESTRATOR_SERVICE_TOKEN`.
4. Restart both services.
5. Revoke any GitHub token used by the read-only adapter if compromise is suspected.
6. Review audit events and edge access logs for unexpected requests.

Rotating either secret invalidates the previous trust path immediately after service reload.

## Validation requirements

CI must cover:

- startup failure without each secret;
- rejection of unauthenticated console requests;
- rejection of direct orchestrator requests;
- rejection of incorrect owner IDs;
- replacement of browser-supplied identity headers;
- fixed audit identity `github:4076926` / `owner-4076926`;
- absence of edge and service secrets in responses and audit events.
