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
  --provider-url http://10.0.0.10:11434/v1 \
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


## Cloudflare Access protected public Provider

For a public API hostname protected by Cloudflare Access, zWorkforce must
provide two independent credentials: an API bearer token for the zwslcore
Provider and a Cloudflare Access **service token pair**. Access must have an
authorized Service Auth policy for this token. Do not bypass Access or
publish the local Ollama TCP port.

The existing zWorkforce Provider adapter now reads the optional variables
`ZWORKFORCE_CF_ACCESS_CLIENT_ID` and
`ZWORKFORCE_CF_ACCESS_CLIENT_SECRET` (legacy single-provider mode).
`ZWORKFORCE_PROVIDER_BASE_URL` must use HTTPS. Both values must be present
together; otherwise startup fails closed. In multi-provider mode, configure
only the names of secret environment variables rather than embedding secrets
inside JSON:

```json
[
  {
    "name": "zwslcore",
    "kind": "openai-compatible",
    "base_url": "https://api.example.com/v1",
    "api_key_env": "ZWSLCORE_PROVIDER_TOKEN",
    "cf_access_client_id_env": "ZWORKFORCE_CF_ACCESS_CLIENT_ID",
    "cf_access_client_secret_env": "ZWORKFORCE_CF_ACCESS_CLIENT_SECRET",
    "priority": 10,
    "models": {
      "luna": "zeaz-free",
      "terra": "zeaz-free",
      "sol": "zeaz-free"
    }
  }
]
```

Provide that JSON as `ZWORKFORCE_PROVIDERS_JSON` through the existing
operator-managed configuration mechanism. Credentials stay in server-side
secret storage or the process environment. The Provider client sends
`CF-Access-Client-Id` and `CF-Access-Client-Secret` only for HTTPS
endpoints, alongside the normal `Authorization: Bearer` Provider key,
and refuses redirects when Cloudflare Access tokens are used.

The optional diagnostic also reads these Access token environment variables
and checks authenticated `/v1/models` / chat inference without printing
secrets:

```bash
python3 scripts/zwslcore-provider-check.py \
  --provider-url https://api.example.com/v1 --model zeaz-free --infer
```

Tests are mock-backed; they do not establish that the Cloudflare Access
application, service-token policy, current DNS route, or Cloud Shell origin
actually exists or is live. Capture external runtime evidence before
declaring Production Stage D complete. Reverting this opt-in configuration
restores the original Provider request path; no data migration is required.

## Scope and rollback

This diagnostic does not modify DNS, Tunnel, Cloudflare Access, SSH, WebUI,
webhook, repositories, provider settings, or databases. It does not read `.env`.
Run `python3 -m unittest tests.test_zwslcore_provider_check -v` for local mocked
contract tests. These tests do not establish external E2E readiness. Production
gates A-I in `docs/PRODUCTION-EVIDENCE.md` remain unchanged.

Rollback: remove this optional script, its tests and documentation; no runtime
migration is necessary.
