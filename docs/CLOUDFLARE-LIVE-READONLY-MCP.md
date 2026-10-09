# Cloudflare Live Read-Only MCP

This is an **opt-in server-side** adapter for a bounded first page of Cloudflare zones, DNS records, or Cloudflare Tunnel inventory. It does not make any modifications.

## Configuration

Configure on the **server only** (prefer the existing secret-reference/mounted environment mechanism). Do not put these values in Git, the browser, or a prompt.

```bash
export ZWORKFORCE_CLOUDFLARE_READ_TENANTS='{
  "tenant-a": {
    "zone_ids": ["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
    "account_ids": ["bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"],
    "token_env": "ZWORKFORCE_CF_TOKEN_PRODUCTION"
  }
}'
# Inject ZWORKFORCE_CF_TOKEN_PRODUCTION through the approved secret manager.
```

These are **illustrative placeholder IDs**, not authoritative ownership claims. The config key is the tenant ID resolved from the authenticated MCP request, not an argument chosen by the client.

## Tool

`cloudflare.live_inventory` accepts `resource` in `zones`, `dns_records`, `tunnels`. The last two require the exact 32-hex-character `resource_id` of an allowlisted zone or account.

Access requires `viewer` role and `workforce:read` scope. The server uses a fixed Cloudflare API origin, GET-only requests, no redirect following, bounded 8-second timeout, 1 MiB response cap, narrow field projections and no token echoes.

Results are explicitly marked `partial: true` because they only include page 1 (up to 50). Never treat this output as a complete inventory or full Cloudflare ownership proof. Zone listing is further filtered to zone IDs on the trusted tenant allowlist.

## Operational boundaries

- Configure an API token with the minimum necessary `Zone Read`, `DNS Read` and/or `Cloudflare Tunnel Read` permissions and resource restrictions.
- This adapter assumes the operator has already reviewed tenant-to-account/zone ownership evidence under `docs/CENTER-CONTROL-PLANE.md`. It does not prove ownership by itself.
- No write endpoints, arbitrary HTTP URLs, mutation approvals, DNS edits or Tunnel creates.
- No live Cloudflare credentials or provider-backed integration evidence were available during development.
- Run the focused test suite, then perform an operator-authorized live read in staging with redacted evidence before production activation.

## Tests

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_cloudflare_live_mcp.py' -v
python3 -m compileall -q zworkforce tests
```
