# Provider Reference

Canonical provider keys for prompt construction, configuration generation, deployment tooling, and operator documentation.

> Documentation and catalog URLs are references. API base URLs are runtime values and must be revalidated before production rollout because providers may introduce regional, account-specific, or model-specific endpoints.

## Hosted providers

| Key | Name | Documentation / catalog | API base or endpoint pattern | Protocol / notes | Credential variable | Gateway status |
|---|---|---|---|---|---|---|
| `nvidia` | NVIDIA NIM / API Catalog | https://build.nvidia.com | `https://integrate.api.nvidia.com/v1` | OpenAI-compatible chat API | `NVIDIA_NIM_API_KEY` | Compatible candidate |
| `groq` | Groq Cloud | https://console.groq.com/docs/models | `https://api.groq.com/openai/v1` | OpenAI-compatible | `GROQ_API_KEY` | Compatible candidate |
| `cerebras` | Cerebras Inference | https://inference-docs.cerebras.ai | `https://api.cerebras.ai/v1` | OpenAI-compatible | `CEREBRAS_API_KEY` | Compatible candidate |
| `sambanova` | SambaNova Cloud | https://docs.sambanova.ai | `https://api.sambanova.ai/v1` | OpenAI-compatible | `SAMBANOVA_API_KEY` | Compatible candidate |
| `openrouter` | OpenRouter | https://openrouter.ai/docs and https://openrouter.ai/api/v1/models | `https://openrouter.ai/api/v1` | OpenAI-compatible; optional attribution headers | `OPENROUTER_API_KEY` | Compatible candidate |
| `github-models` | GitHub Models | https://models.github.ai/catalog/models | `https://models.github.ai/inference` | OpenAI SDK-compatible inference surface; token scopes and rate limits apply | `GITHUB_MODELS_TOKEN` | Verify path behavior |
| `mistral` | Mistral La Plateforme | https://docs.mistral.ai | `https://api.mistral.ai/v1` | OpenAI-compatible chat surface | `MISTRAL_API_KEY` | Compatible candidate |
| `codestral` | Codestral | https://docs.mistral.ai/capabilities/code_generation/ | `https://codestral.mistral.ai/v1` | OpenAI-compatible deployment; distinct entitlement/key may apply | `CODESTRAL_API_KEY` | Compatible candidate |
| `scaleway` | Scaleway Generative APIs | https://www.scaleway.com/en/docs/generative-apis/ | Provider/region endpoint from Scaleway console; commonly an OpenAI-compatible `/v1` base | Regional/account-specific | `SCALEWAY_API_KEY` | Operator endpoint required |
| `googleai` | Google AI Studio / Gemini | https://ai.google.dev/gemini-api/docs/openai | `https://generativelanguage.googleapis.com/v1beta/openai` | OpenAI compatibility layer | `GEMINI_API_KEY` | Compatible candidate |
| `zai` | Z.ai | https://docs.z.ai | OpenAI-compatible base from current Z.ai docs; Anthropic-compatible deployments may use `https://api.z.ai/api/anthropic/v1` | Multiple API dialects; do not infer transport from credential presence | `ZAI_API_KEY` | Adapter/path verification required |
| `qwen` | Alibaba DashScope / Model Studio | https://help.aliyun.com/zh/model-studio/ | China: `https://dashscope.aliyuncs.com/compatible-mode/v1`; international: `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | OpenAI-compatible; choose endpoint by account region | `DASHSCOPE_API_KEY` | Compatible candidate |
| `cloudflare` | Cloudflare Workers AI | https://developers.cloudflare.com/workers-ai/models/ | `https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1` | Account-scoped OpenAI-compatible endpoint | `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` | Template expansion required |
| `ovhcloud` | OVHcloud AI Endpoints | https://endpoints.ai.cloud.ovh.net | Endpoint generated for the selected deployment/model in OVHcloud AI Endpoints | Model/deployment-specific; OpenAI compatibility depends on serving image | `OVHCLOUD_API_KEY` | Operator endpoint required |
| `opencode-zen` | OpenCode Zen | https://opencode.ai/docs/zen/ | `https://opencode.ai/zen/v1` | OpenAI-compatible service surface | `OPENCODE_API_KEY` | Compatible candidate |
| `opencode-go` | OpenCode Go | https://opencode.ai/docs/zen/ | `https://opencode.ai/zen/go/v1` | Shares OpenCode credential | `OPENCODE_API_KEY` | Verify supported paths/models |
| `deepseek` | DeepSeek | https://api-docs.deepseek.com | OpenAI: `https://api.deepseek.com/v1`; Anthropic compatibility: `https://api.deepseek.com/anthropic` | Select one dialect explicitly | `DEEPSEEK_API_KEY` | OpenAI path compatible candidate |
| `kimi` | Moonshot AI / Kimi | https://platform.moonshot.ai/docs | OpenAI-compatible endpoint from the account region; Anthropic-compatible deployments may use `https://api.moonshot.ai/anthropic/v1` | Endpoint availability can be account/region specific | `KIMI_API_KEY` | Adapter/path verification required |
| `wafer` | Wafer | Provider documentation/console | `https://pass.wafer.ai/v1/messages` | Native Anthropic Messages endpoint | `WAFER_API_KEY` | Dedicated Messages transport required |
| `fireworks` | Fireworks AI | https://docs.fireworks.ai | `https://api.fireworks.ai/inference/v1` | OpenAI-compatible inference; model paths/IDs vary | `FIREWORKS_API_KEY` | Compatible candidate |

## Local providers

| Key | Name | Documentation | Default API base | Protocol / notes | Credential variable | Gateway status |
|---|---|---|---|---|---|---|
| `lm-studio` | LM Studio | https://lmstudio.ai/docs | `http://localhost:1234/v1` | OpenAI-compatible local server | None by default | Compatible candidate; use host-reachable address from Compose |
| `llamacpp` | llama.cpp server | https://github.com/ggml-org/llama.cpp/tree/master/tools/server | `http://localhost:8080/v1` | OpenAI-compatible local server | None by default | Compatible candidate; use host-reachable address from Compose |
| `ollama` | Ollama | https://docs.ollama.com/api/openai-compatibility | `http://localhost:11434/v1` | OpenAI-compatible endpoint; native Ollama API also exists at the root service | None by default | Compatible candidate; use host-reachable address from Compose |

## Model-catalog conventions

For OpenAI-compatible providers, try `{base_url}/models` only when the provider documents that endpoint. Do not assume every provider exposes model discovery or returns the same schema. Providers with web-only catalogs, deployment-specific models, or account-filtered catalogs must be queried through their documented control plane.

## Prompt-generation rules

- Use the exact `Key` value as the stable machine-facing identifier.
- Include both the provider key and protocol when generating configuration, for example `openrouter + openai-compatible`.
- Use the provider's current model catalog rather than embedding a permanent model list in prompts.
- Treat documentation URLs as references, not API base URLs.
- Preserve endpoint templates such as `{account_id}` and require operators to supply the value.
- Never include populated credential values in prompts, logs, issues, artifacts, or committed files.
- Credential availability does not imply that the AI Gateway has a compatible transport adapter.
- Add providers to `UPSTREAM_PROVIDERS_JSON` only after confirming endpoint path, authentication scheme, request dialect, streaming behavior, upload support, quota semantics, and failover safety.
- Native Anthropic Messages endpoints must not be inserted into the current OpenAI chat chain until the gateway has a dedicated `/v1/messages` transport.

## Current gateway boundary

The current AI Gateway transport targets `/v1/chat/completions`. Providers marked **Compatible candidate** still require live credential, model, streaming, quota, and failover verification before production enablement. Native Anthropic Messages-only or provider-specific APIs require a dedicated transport adapter and regression tests.