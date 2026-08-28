# ZeaZ Provider

Current release candidate: `0.4.0rc1`.

Standalone multi-provider AI gateway with two client-compatible surfaces:

- Anthropic Messages API: `POST /v1/messages`
- OpenAI Chat Completions: `POST /v1/chat/completions`
- OpenAI Responses/Codex: `POST /v1/responses`
- shared model discovery: `GET /v1/models`

It is an API gateway, not a foundation model. It keeps provider credentials
server-side and maps stable local model aliases to native Anthropic, native
OpenAI Responses, Azure, Ollama, LiteLLM, or any OpenAI-compatible endpoint.

## Supported integrations

Presets are included for Anthropic, OpenAI, Ollama, LiteLLM, OpenRouter,
Gemini, Azure OpenAI, Groq, Mistral, DeepSeek, xAI, Together, Fireworks,
NVIDIA NIM, Perplexity, and a configurable custom provider.

Any service implementing `/chat/completions` can be added without changing
source:

```yaml
providers:
  my-provider:
    api: openai
    base_url: https://provider.example/v1
    api_key: ${MY_PROVIDER_API_KEY}

models:
  my-model:
    provider: my-provider
    model: provider-model-id
```

Every public model name follows `zeaz-<name>`. Upstream model IDs stay private
in the route configuration, so applications do not change when a backend model
or provider is replaced. Included aliases cover `zeaz-auto`, `zeaz-local`,
`zeaz-free`, `zeaz-claude`, `zeaz-codex`, `zeaz-openrouter`, `zeaz-gemini`, `zeaz-azure`,
`zeaz-qwen-free`, `zeaz-kimi-free`, `zeaz-openrouter-free-all`,
`zeaz-free-<provider-model>`, `zeaz-groq`, `zeaz-mistral`, `zeaz-deepseek`,
`zeaz-xai`, `zeaz-together`, `zeaz-fireworks`, `zeaz-nvidia`,
`zeaz-perplexity`, and `zeaz-custom`.

Provider `api` values:

- `anthropic`: native `/messages`
- `responses`: native OpenAI `/responses`
- `openai`: OpenAI-compatible `/chat/completions`
- `azure`: Azure `/chat/completions` with `api-key` and `api-version`

## Quick start

```bash
make env-init
# Edit .env and config/providers.yaml.
make install
make validate
make run
```

Container:

```bash
make env-init
docker compose config --quiet
make up
make health
```

The production container runs as the dedicated UID/GID `10001`, drops all
Linux capabilities, sets `no-new-privileges`, mounts its root filesystem
read-only, and permits writes only to a size-limited `/tmp` tmpfs. The provider
configuration mount is read-only and the published port is loopback-only.
After building `zeaz/provider:0.4.0`, verify the effective runtime—not just the
Compose declarations—with:

```bash
make validate-container
```

Python runtime, development, and build dependencies are exact-version locked
with SHA-256 hashes. `make install` enforces the build and development locks,
and the container build installs only hash-verified runtime artifacts. To
review an intentional dependency update, install `pip-tools` in the virtual
environment, run `make lock`, inspect all three lockfile changes, and rerun the
validation and no-cache container gates.

Both build stages pin the Python base image by SHA-256 digest. Treat digest
updates as reviewed dependency changes: resolve the current official
`python:3.12-slim-bookworm` manifest, update every `FROM` line to the same
verified digest, then run the no-cache build and runtime validation. The
`.dockerignore` excludes `.env`, live provider configuration, virtualenvs,
repository metadata, caches, and build artifacts from the daemon context.

## Standalone installer

The release contains a versioned installer derived from deterministic installer
requirements, not copied implementation:

```bash
make install-dry-run
CONFIRM_INSTALL=yes make install-systemd
```

It installs under `~/.local/share/zeaz-provider/versions/<version>`, retains
existing provider configuration, and atomically switches `current`. New
versions are built and import-tested in a private staging directory. Signals
remove partial staging, and any failure after the switch restores the previous
`current` target automatically.

## Verified update and auto-update

Updates require an operator-controlled HTTPS JSON manifest containing version,
release URL, and SHA-256, plus a detached Ed25519 signature. Keep the private
key offline and configure each host with only the public key. Checking verifies
the exact manifest bytes before parsing them and never mutates the installation:

```bash
export ZEAZ_UPDATE_MANIFEST_URL=https://example.com/zeaz-provider/latest.json
export ZEAZ_UPDATE_PUBLIC_KEY=/etc/zeaz-provider/update-signing-key.pub
make update-check
CONFIRM_UPDATE=yes make update
```

The signature URL defaults to `${ZEAZ_UPDATE_MANIFEST_URL}.sig`; set
`ZEAZ_UPDATE_SIGNATURE_URL` to use another HTTPS location. Release operators
can create it with:

```bash
make sign-update-manifest \
  MANIFEST=dist/latest.json \
  PRIVATE_KEY=/secure/offline/update-signing-key.pem
```

Daily auto-update is opt-in:

```bash
CONFIRM_AUTO_UPDATE=yes make auto-update
```

The timer downloads only over HTTPS and applies a release only after manifest
signature and artifact SHA-256 verification. Review
[`docs/UPGRADE_SOURCES.md`](docs/UPGRADE_SOURCES.md) for the five inspected
source repositories, commit pins, accepted behaviors, exclusions, and roadmap.

Host preparation for Ubuntu 26.04 is read-only by default:

```bash
python3 -m zeaz_infra.host --plan
python3 -m zeaz_infra.host --json --plan
bash scripts/doctor.sh
bash scripts/uninstall.sh --dry-run
make host-bootstrap-dry-run
```

The host planner reports CPU, memory, disk, virtualization, NVIDIA/AMD/CPU-only
mode, Docker Engine from the official repository, optional NVIDIA Container
Toolkit, VMware guest integration, conservative sysctl and filesystem tuning,
UFW defaults, systemd service hooks, health checks, and reversible uninstall
behavior. The apply paths remain separate and dry-run-first.

On a fresh Ubuntu 26.04 VMware guest, review the dry-run output first, then
apply host setup as root while naming the unprivileged account that runs the
gateway. This installs Docker and, only when selected and driver-supported, the
NVIDIA runtime; it keeps gateway ports closed and preserves SSH access.

```bash
sudo bash scripts/bootstrap-host.sh --dry-run
sudo bash scripts/bootstrap-host.sh --apply --install-user "$USER"
```

The bootstrap does not invent an update channel. To enable the daily update
timer, provide a reviewed HTTPS manifest and its Ed25519 public key:

```bash
sudo bash scripts/bootstrap-host.sh --apply --install-user "$USER" \
  --update-manifest-url https://releases.example/manifest.json \
  --update-public-key /etc/zeaz/release-public-key.pem
```

The remaining I1 acceptance test must run on a manually created, fresh Ubuntu
26.04 VMware snapshot. Its runner is dry-run-first and deliberately excludes
local configuration and `.env` files from the transfer:

```bash
make vm-snapshot-dry-run VM_HOST=ubuntu@vm.example VM_INSTALL_USER=zeaz
bash scripts/test-vm-snapshot.sh --apply --host ubuntu@vm.example --install-user zeaz \
  --identity-file /absolute/path/vm-identity \
  --update-manifest-url https://releases.example/manifest.json \
  --update-public-key /etc/zeaz/release-public-key.pem
```

The runner defaults to passwordless sudo because it is designed for unattended
acceptance testing. A human running it in a terminal may explicitly use
`--sudo-mode interactive`; this allocates a TTY and prompts on the VM. Codex
does not use interactive mode because it cannot supply a remote sudo password.

The Compose port binds to loopback. Place it behind Cloudflare Tunnel, Traefik,
Caddy, or another authenticated TLS reverse proxy for remote access.

## Anthropic client

```python
from anthropic import Anthropic

client = Anthropic(
    api_key="your-zeaz-client-key",
    base_url="http://127.0.0.1:8080",
)
message = client.messages.create(
    model="zeaz-claude",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}],
)
print(message.content[0].text)
```

Use `zeaz-local` to send the same Anthropic request format to Ollama. Non-native
Messages requests are converted to Chat Completions for non-streaming calls.

## OpenAI and Codex-compatible clients

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-zeaz-client-key",
    base_url="http://127.0.0.1:8080/v1",
)

response = client.responses.create(
    model="zeaz-codex",
    input="Review this function",
)
print(response.output_text)
```

`zeaz-codex` routes to a native Responses provider. Chat Completions clients
can use the same base URL and model aliases.

## Authentication

Production configuration should contain only comma-separated SHA-256 digests
of high-entropy gateway client keys:

```dotenv
ZEAZ_CLIENT_KEY_HASHES=sha256:<64-hex-characters>,sha256:<64-hex-characters>
```

Generate a digest without exposing the key in process arguments:

```bash
make client-key-hash
```

Both `x-api-key` and `Authorization: Bearer` are accepted. The gateway refuses
all authenticated endpoints when no client keys are configured. Local
unauthenticated development requires the explicit
`ZEAZ_ALLOW_UNAUTHENTICATED=true` setting.

The legacy `ZEAZ_CLIENT_KEYS` setting remains available for migration, but its
values are hashed immediately during startup and are never retained in runtime
settings. Verification hashes the presented key and compares every configured
digest using constant-time comparisons. Use randomly generated keys of at
least 32 characters because unsalted SHA-256 does not protect weak keys from
offline guessing.

## Audit events

Every HTTP request emits a single-line JSON audit event on the
Uvicorn error logger. Events contain only a request ID digest, a known
HTTP method and route name, status, elapsed time, rate-limit result, and a
SHA-256 client identity. Query strings, headers, bodies, prompts, credentials,
provider details, and raw errors are never included. Unknown paths and methods
are recorded as `unmatched` and `OTHER`.

## Metrics

Prometheus metrics are available at `GET /metrics` and use bounded route,
method, and status labels; prompts, credentials, model IDs, arbitrary paths,
and client identifiers are excluded. Set `ZEAZ_METRICS_ENABLED=false` to
disable scraping.

Optional OpenTelemetry OTLP/HTTP metric export is enabled by setting
`OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`. Standard OpenTelemetry exporter
environment variables configure authentication, TLS, and export intervals.
The Prometheus registry is process-local; use one gateway worker for direct
scraping, or use OTLP export when running multiple workers.

## Rate limiting

The default in-memory sliding-window limiter is suitable for one worker. Every
multi-worker or multi-host deployment must use the shared Redis backend:

```dotenv
ZEAZ_RATE_LIMIT_PER_MINUTE=120
ZEAZ_RATE_LIMIT_BACKEND=redis
ZEAZ_REDIS_URL=rediss://user:password@redis.example:6379/0
ZEAZ_RATE_LIMIT_KEY_PREFIX=zeaz:rate-limit:
```

Redis decisions use one atomic server-side operation and Redis server time.
Backend errors fail closed with a sanitized `503`; the gateway never silently
falls back to per-process limits. Keep Redis private, require authentication
and TLS outside a trusted local network, and supply its URL through the
environment or a secret manager.

## Cloudflare trusted proxies

Forwarded client headers are ignored by default. To use Cloudflare's
`CF-Connecting-IP` for client rate-limit identity, configure only the CIDRs
from which this gateway directly receives Cloudflare traffic:

```dotenv
ZEAZ_TRUSTED_PROXY_CIDRS=192.0.2.0/24,2001:db8::/32
```

Replace these documentation-only networks with the current Cloudflare proxy
CIDRs or, for a local Cloudflare Tunnel, the narrowly scoped address used by
the tunnel process. Never trust a broad local network when untrusted clients
can reach the origin directly. Invalid, multiple, or non-IP header values are
ignored, and unmatched peers always retain their direct socket address.

## Request and response limits

`ZEAZ_MAX_CONCURRENT_REQUESTS` bounds active requests per worker. Admission is
fail-fast: excess requests receive a sanitized `503` and `Retry-After: 1`;
streaming requests hold their slot until the stream closes or disconnects.

`ZEAZ_MAX_RESPONSE_BYTES` bounds provider JSON before parsing, provider error
bodies before logging or classification, raw provider streams, translated SSE
streams, and final non-streaming gateway responses. Oversized non-streaming
responses return a bounded `502`; an SSE stream that crosses the limit is
terminated without emitting the oversized chunk. The minimum configurable
response budget is 1024 bytes.

## Local-first free fallback

`zeaz-free` works through both Anthropic Messages and OpenAI/Codex request
surfaces. It uses the configured Ollama model first:

```text
Ollama → OpenRouter free route → Gemini free-tier route → Groq free-tier route
```

Cloud fallback is disabled by default because it can send prompts and file
content outside the machine. Enable it explicitly:

```dotenv
ZEAZ_LOCAL_MODEL=qwen3:8b
FREE_CLOUD_FALLBACK_ENABLED=true
OPENROUTER_API_KEY=...
GEMINI_API_KEY=...
GROQ_API_KEY=...
```

`zeaz-qwen-free` is the Qwen-specific free route. It uses
`ZEAZ_QWEN_LOCAL_MODEL` locally, defaulting to `qwen3:8b`, and falls back to
`OPENROUTER_QWEN_FREE_MODEL` when free cloud fallback is enabled. If
OpenRouter has no Qwen `:free` model available, leave the default
`openrouter/free` router or set the variable to the current free Qwen model ID.

`zeaz-kimi-free` is the Kimi-specific free route. It uses
`ZEAZ_KIMI_LOCAL_MODEL` locally, defaulting to `kimi-k2:latest`, and falls back
to `OPENROUTER_KIMI_FREE_MODEL` when free cloud fallback is enabled. If
OpenRouter has no Kimi `:free` model available, leave the default
`openrouter/free` router or set the variable to the current free Kimi model ID.

`zeaz-openrouter-free-all` connects every zero-price model returned by
OpenRouter's public model catalog on 2026-07-30, using `openrouter/free` first
and each specific free model as a fallback. Each model also has a direct
`zeaz-free-<provider-model>` alias, such as `zeaz-free-openai-gpt-oss-20b` and
`zeaz-free-google-gemma-4-31b-it`. These cloud-only routes are present only
when `FREE_CLOUD_FALLBACK_ENABLED=true`.

Free tiers, quotas, available models, and provider terms can change. The
gateway does not claim that external calls are permanently free. Configure
current provider model IDs in `.env`. Non-streaming calls automatically move
to the next route for missing models, rate limits, timeouts, and transient
upstream failures. Authentication and invalid-request errors do not silently
fall through.

## Streaming limitation in 0.2

Streaming is passed through without buffering when the selected backend uses
the same protocol as the client:

- Anthropic Messages client → native Anthropic backend
- OpenAI Chat client → OpenAI-compatible backend
- Responses/Codex client → native Responses backend

Cross-protocol non-streaming conversion is implemented. Cross-protocol
stream-event translation is intentionally deferred rather than emitting
incorrect event contracts.

## Production checklist

- Replace the generated client key and configure only providers in use.
- Use separate keys per provider and environment.
- Pin dependency locks and container image digests.
- Keep the port loopback-only or on a private proxy network.
- Require Cloudflare Access or equivalent outer authentication.
- Rate-limit by client key at the reverse proxy.
- Never log request authorization headers or provider credentials.
- Disable cloud fallbacks for data that must stay local.
