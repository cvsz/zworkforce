# zwslcore Provider and zWorkforce MCP Interoperability

This is an optional, read-only verification path. zWorkforce owns its existing
identity, tenant authorization, MCP endpoint and provider pool; zwslcore owns
the existing local model runtime and Provider Gateway. Do not deploy a second
provider router, duplicate MCP server or copy `.env` files across repositories.

## Read-only verification

From the actual zWorkforce host, check an approved authenticated Provider:

```bash
python3 scripts/zwslcore-provider-check.py \
  --provider-url https://provider.example.com/v1 \
  --model qwen2.5-coder:7b
```

For a strictly private Cloudflare WARP/VPN network with verified routing,
explicitly opt into private HTTP:

```bash
python3 scripts/zwslcore-provider-check.py \
  --provider-url http://10.88.0.3:11434/v1 \
  --allow-private-http --model qwen2.5-coder:7b
```

Cloud Shell private IPs are ephemeral. The example address is not assumed
reachable; only a successful probe from the actual zWorkforce host is evidence.
Do not expose unauthenticated Ollama publicly. For production use authenticated
HTTPS Provider endpoints and the existing zWorkforce Provider configuration.
The optional `--infer` flag adds a small actual chat-completion request.

Verify the existing authenticated MCP contract separately, with a token
supplied in the process environment rather than as a CLI argument:

```bash
read -rsp 'MCP token: ' ZWORKFORCE_MCP_TOKEN; echo
export ZWORKFORCE_MCP_TOKEN
python3 scripts/zwslcore-provider-check.py \
  --mcp-url https://workforce.example.com/mcp
unset ZWORKFORCE_MCP_TOKEN
```

The probe performs modern `server/discover` using the documented
`2026-07-28` MCP request metadata. It never calls mutating tools, follows
redirects or prints response bodies or credentials. A nonzero exit status
means that the selected check was not verified.

## Scope and rollback

This diagnostic does not modify DNS, Tunnel, Cloudflare Access, SSH, WebUI,
webhook, repositories, provider settings, or databases. It does not read `.env`.
Run `python3 -m unittest tests.test_zwslcore_provider_check -v` for local mocked
contract tests. These tests do not establish external E2E readiness. Production
gates A-I in `docs/PRODUCTION-EVIDENCE.md` remain unchanged.

Rollback: remove this optional script, its tests and documentation; no runtime
migration is necessary.
