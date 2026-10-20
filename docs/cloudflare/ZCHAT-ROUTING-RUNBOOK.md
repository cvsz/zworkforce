# ZChat Cloudflare route ownership and recovery

Owner: **zWorkforce** (DNS, Cloudflare Tunnel, route reconciliation, approvals).
Application owner: **cvsz/zchat** (Control Server, website/UI, application health).

## Observed incident (2026-10-17)

- The `zwslcore` tunnel (`45667e7e-7383-4265-b53e-6a9e770a8554`) had three active edge connections.
- Public `https://zchat.zeaz.dev/` returned a JSON 404 after the earlier 1033 resolved.
- Control Server at `127.0.0.1:8000` returned the same JSON 404 on `/`, `/health`, `/ready`, `/docs`, and `/openapi.json`.
- Local Caddy served an empty 200 response for `Host: zchat.zeaz.dev` because its host configuration only covered `zwsl.zeaz.dev` and `zmovie.zeaz.dev`.
- The checked-in `deploy/cloudflare/tunnel-ingress.yml` did **not** declare a ZChat host route.
- The running connector uses a **token-file**; its remote-managed published routes are not proven to match the checked-in ingress manifest.

## Safe audit

Run in the actual origin host environment:

```bash
bash scripts/cloudflare-zchat-audit.sh
```

The script is **read-only** and prints HTTP status codes rather than response bodies. By default it does not invoke `cloudflared` or use its stored credentials. To explicitly include active connector details, set `ZCHAT_INCLUDE_TUNNEL_INFO=1`; `cloudflared tunnel info` may use the configured account certificate. That inventory reports connectors, not remote-managed published routes. The script creates no DNS records, restarts no services, and mutates no production infrastructure. See [Cloudflare tunnel permissions](https://developers.cloudflare.com/tunnel/features/locally-managed-tunnels/tunnel-permissions/) and [useful tunnel commands](https://developers.cloudflare.com/tunnel/features/locally-managed-tunnels/tunnel-useful-commands/) for credential scope and command behavior.

## Promotion gates

1. Confirm Cloudflare live DNS and remote-managed Published Application Routes using the existing tenant-scoped read-only integration. Do not assume a local ingress YAML controls a token-managed tunnel.
2. Confirm the intended origin: API-only `127.0.0.1:8000` or a separately deployed Web UI with `/api` forwarding. An HTTP 404 on `/` is **not** evidence of a broken tunnel.
3. If Caddy routing is required, manage its host Caddyfile separately, validate the proposed config, snapshot it, and confirm the Cloudflare route actually targets Caddy.
4. Obtain the canonical independent approval and apply via the existing `scripts/cloudflare-plan.sh` / `scripts/cloudflare-apply.sh` workflow, where Terraform owns the resource. Do not mutate Cloudflare through this document or audit script.
5. Verify exact intended application endpoints and public HTTPS with a rollback plan, record redacted evidence, and avoid affecting other `zeaz.dev` hosts.

No production Cloudflare mutation is authorized by this change.
