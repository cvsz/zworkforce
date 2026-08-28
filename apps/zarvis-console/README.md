# Z.A.R.V.I.S. Console

A private browser command center for the first Z.A.R.V.I.S. vertical slice.

This deployment is permanently bound to GitHub user ID `4076926` (`cvsz`). There is no sign-up, invitation, secondary user, shared workspace, or runtime owner override.

- Accepts typed commands and optional browser speech recognition.
- Sends only the transcript and session metadata to the same-origin console server.
- Proxies requests to `services/zarvis-orchestrator`.
- Uses browser speech synthesis for the speech-ready response.
- Displays the repository result and audit event identifier.
- Never exposes `GITHUB_TOKEN`, edge secrets, service tokens, or provider credentials to browser JavaScript.
- Rejects every non-health route unless a trusted edge supplies the fixed owner ID and correct edge secret.

## Owner-only boundary

A trusted identity edge must authenticate the owner, remove any incoming `x-zarvis-*` headers, and inject:

```text
x-zarvis-owner-id: 4076926
x-zarvis-edge-secret: <server-side secret>
```

The origin must not be reachable directly from the public internet. See `docs/security/zarvis-owner-access.md`.

## Run

Generate two independent secrets with at least 32 random bytes each. Start the orchestrator first, then the console:

```bash
export ZARVIS_EDGE_SHARED_SECRET='<edge-only-random-secret>'
export ZARVIS_ORCHESTRATOR_SERVICE_TOKEN='<independent-service-token>'

pnpm --filter @z-platform/zarvis-orchestrator start
ZARVIS_ORCHESTRATOR_URL=http://127.0.0.1:8094 \
  pnpm --filter @z-platform/zarvis-console start
```

The command center intentionally returns `403 owner_access_denied` without the trusted edge assertion. `GET /healthz` remains available for infrastructure health checks.

Browser speech recognition is an optional convenience. Typed commands remain the deterministic supported path, and browser audio is not uploaded by this application.
