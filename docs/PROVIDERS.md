# Providers

zWorkforce supports OpenAI-compatible `/chat/completions` providers and a deterministic built-in mock provider.

Each provider can define `name`, `kind`, `base_url`, `api_key` or `api_key_env`, `priority`, `timeout_seconds`, `retries`, `models.luna|terra|sol`, and `enabled`.

At runtime the pool tries healthy providers in ascending priority. Providers without a model for the requested tier are skipped. Consecutive failures open a temporary circuit; a healthy fallback can serve the turn. Health derives from real calls rather than synthetic requests that could consume quota.

Provider pricing is intentionally not fetched automatically in v2. Credit rates are explicit configuration so accounting remains deterministic and auditable when external prices change.

## Cloudflare Access service tokens

Existing OpenAI-compatible endpoints can optionally send a Cloudflare Access
service token pair for Zero Trust protected HTTPS Provider Gateways. The
single-provider environment keys are `ZWORKFORCE_CF_ACCESS_CLIENT_ID`
and `ZWORKFORCE_CF_ACCESS_CLIENT_SECRET`. For
`ZWORKFORCE_PROVIDERS_JSON`, pass the environment variable **names**
through `cf_access_client_id_env` and `cf_access_client_secret_env`
fields; actual values stay in server-side secret storage. Partial pairs and
plaintext HTTP are rejected. When configured, authenticated requests send
the two Cloudflare Access headers without following redirects, plus the
existing Provider Bearer API token. No Access token is needed for Providers
without Access and their previous behavior is preserved.
