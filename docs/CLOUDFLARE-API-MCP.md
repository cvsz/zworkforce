# Cloudflare API MCP for zWorkforce

## Status

A **documentation and planning-only** Cloudflare MCP integration is implemented in the existing authenticated zWorkforce `POST /mcp` endpoint. **It does not connect to Cloudflare or modify infrastructure.**

## Official references

- [Cloudflare API overview](https://developers.cloudflare.com/api/overview/)
- [API permissions](https://developers.cloudflare.com/fundamentals/api/reference/permissions/)
- [Token creation](https://developers.cloudflare.com/fundamentals/api/how-to/create-via-api/)
- [Cloudflare Tunnel](https://developers.cloudflare.com/tunnel/get-started/)

## Implemented MCP tools

| Tool | Description | Required authorization |
| --- | --- | --- |
| `cloudflare.references` | Curated documentation URLs and API base | viewer + workforce:read |
| `cloudflare.operation_plan` | Operation methods, canonical endpoint paths, least privilege and approval requirements | viewer + workforce:read |

Allowed operation IDs: `dns.list`, `zone.get`, `tunnel.list`, `dns.create`, `dns.delete`, `tunnel.create`.

Both tools are non-mutating. `operation_plan` with a write operation **only outputs a proposed plan**. It does not fetch, generate credentials, execute or approve the plan.

## Security and ownership

- Do not infer resource ownership from the `zeaz.dev` suffix or from a zone-scoped token. Verify ownership in Terraform and the center-control inventory contract before implementation.
- Never embed Cloudflare API tokens in prompts, browser code or Git. Tokens belong to secret-reference-backed server-side runtimes.
- Use Cloudflare API tokens rather than global API keys, and narrow permissions to individual zones/accounts.
- Future writes must require immutable plan digest, explicit operator approval, exact resource allowlist, tenant-scoped identity, audit trail and post-action verification.
- Block mutation and live secret access in this phase. An AI agent must not use a separate shell/HTTP tool to circumvent policy gates.
- Never pass arbitrary URLs or paths to a Cloudflare request handler. Restrict to documented HTTPS endpoints and validated IDs.
- Keep the existing `scripts/cloudflare-plan.sh` and `scripts/cloudflare-apply.sh` controls authoritative. MCP does not replace the Terraform review process.

## Example

```bash
export ZWORKFORCE_MCP_TOKEN="(read from your approved secret manager)"
zworkforce mcp-call https://workforce.example.com/mcp cloudflare.references --arguments '{}'
zworkforce mcp-call https://workforce.example.com/mcp cloudflare.operation_plan --arguments '{"operation":"dns.list"}'
```

## Tests

```bash
PYTHONPATH=. python -m unittest discover -s tests -p 'test_cloudflare_api_mcp.py' -v
python -m compileall -q zworkforce tests
```

Follow-up implementation of **live API read access** must add a tenant-bound Cloudflare credential store, resource ownership registry, network egress restrictions, sanitized responses, rate limiting and genuine provider integration tests. Do not label it working until the live evidence is available.
