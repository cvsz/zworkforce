# Open WebUI Customer-Facing Security Boundary

**Status:** Source-level containment candidate; not a deployment authorization.

## Fail-closed configuration

The Compose definition intentionally requires two operator-managed values:

- `WEBUI_SECRET_KEY`: unique, high-entropy session-signing secret supplied through the approved secret manager.
- `OPEN_WEBUI_PROVIDER_API_KEY`: dedicated least-privilege credential for the Open WebUI-to-zWorkforce provider route. Do not reuse a broad platform or administrator token.

Compose rendering must fail when either value is missing or empty. CI uses dummy values only; no production secret is stored in the repository.

The customer-facing defaults are:

- `WEBUI_AUTH=true`
- `ENABLE_SIGNUP=false`
- `DEFAULT_USER_ROLE=pending`
- Code execution, HTML preview, artifacts, Functions and OpenAPI integration disabled.
- Host port bound to `127.0.0.1` only. The existing Caddy route remains the only host-side upstream and proxies to `127.0.0.1:3080`.

Do not expose container port 8080 or host port 3080 directly on a LAN/public interface. The Cloudflare Tunnel must continue to terminate at the reviewed loopback Caddy origin; this source change does not modify DNS, Tunnel configuration, Terraform state, or live routes.

## Persistent configuration and operator acceptance

Open WebUI persists configuration and user state in `open-webui-data`. Environment defaults alone do not prove the persisted application state is safe. Before any approved maintenance-window rollout, an operator must:

1. Inventory existing users and administrators without exporting passwords, tokens, or session material.
2. Verify persisted authentication, signup, default-role, tool and integration settings after startup.
3. Confirm no untrusted account can obtain the `admin` role.
4. Verify remote/LAN access to host port 3080 is rejected while the Caddy loopback route remains reachable.
5. Verify provider requests fail closed with missing/invalid credentials and succeed only with the dedicated least-privilege credential.
6. Rotate the session secret and revoke affected sessions if the previous tracked fallback was ever used.
7. Rotate/revoke the previous tracked provider-like value if it was ever deployed; its validity is not established by source inspection.

The image still uses the floating `ghcr.io/open-webui/open-webui:main` reference. A reviewed immutable release/digest is a separate release blocker; do not infer an image digest from a tag.

There is also source-level port drift in the existing deployment documentation/Terraform examples (3080 versus 3000). This candidate preserves the Caddy-to-3080 contract and does not run Terraform or change Tunnel routing. Reconcile the declared origin through a separate reviewed infrastructure plan before any apply.

## Rollback

Do not restart or reconfigure the live service as part of this PR. If the candidate fails in an isolated staging environment, revert the candidate through a reviewed PR and restore the prior Compose file only in that isolated environment.

Never restore a committed session-secret/provider-token fallback, public host-port binding, admin-by-default signup, or untrusted code execution/Functions/OpenAPI settings as a production rollback. Keep customer traffic blocked until the operator verifies persistent settings, secret injection, Caddy/Tunnel access controls, and an independently reviewed immutable image.

No production database, persistent volume, credential, user account, DNS record, Cloudflare route, payment, ad spend, or deployment is changed by this source-only candidate.
