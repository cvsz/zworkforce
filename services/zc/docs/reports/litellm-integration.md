# LiteLLM Integration Contract

## Scope

`zc` remains the application boundary for authentication, tenant isolation,
agents, skills, files, and workflows. LiteLLM runs as a process-local Python
Router when `AI_PROVIDER=litellm`.

The integration was derived from the local LiteLLM source checkout at
`/home/zeazdev/litellm`, including:

- `litellm/proxy/proxy_server.py` for authenticated model discovery;
- `litellm/proxy/response_api_endpoints/endpoints.py` for Responses API
  capabilities;
- `litellm/proxy/health_endpoints/` for liveness contracts;
- `litellm/types/llms/openai.py` for normalized message and usage shapes; and
- `docker/Dockerfile.non_root` for the local non-root runtime image.

No LiteLLM source files are copied into or modified by `zc`.

## Supported Contract

| Capability | LiteLLM endpoint | `zc` behavior |
|---|---|---|
| Text generation | `Router.acompletion()` | Adds application-owned system context and returns a stable AI resource |
| Model discovery | `Router.get_model_names()` | Returns sanitized model aliases through authenticated `GET /v1/ai/models` |
| Usage | Chat-completion `usage` | Maps prompt and completion tokens to `AIUsage` |
| Readiness | Router initialization | Adds a sanitized `ai_provider` readiness component |

The LiteLLM Responses API is intentionally not proxied directly. Exposing it
would bypass the bounded `zc` request model and application authorization
semantics. It may be adopted later through a dedicated resource contract for
background responses, tools, and stored response ownership.

## Security Boundaries

- No LiteLLM proxy, listener, or master key exists.
- Clients never supply provider credentials.
- Provider errors are mapped to stable `zc` errors without returning upstream
  response bodies.
- Model discovery returns aliases only, not deployment metadata or provider
  credentials.
- Docker Compose starts only the `zc` service.
- Provider credentials are resolved from process environment references in
  `litellm-config.yaml`.

## Runtime

The sibling-source layout is:

```text
/home/zeazdev/
├── litellm/
└── zc/
```

The packaged runtime pins `litellm==1.94.0rc1`, the newest installable 1.94
pre-release compatible with the audited local source
version. The sibling checkout is evidence and a development reference; it is
not a second runtime service.

The integration does not require LiteLLM's database, Redis, dashboard, spend
tracking, or enterprise package. Those capabilities remain disabled unless a
separate design and cost review approves them.
