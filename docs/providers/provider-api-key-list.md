# Provider API Key Acquisition List

This document lists where operators can create or manage provider credentials used by Z Platform. It does not contain real credentials and does not enable any provider automatically.

> Security rule: create keys only in the provider's official console, store them in an approved secret manager or local `.env`, and never paste populated values into GitHub, issues, logs, screenshots, prompts, or browser-delivered configuration.

## Provider list (A–Z)

| Provider | Environment variable | Create/manage credential | Documentation | Notes |
|---|---|---|---|---|
| Alibaba DashScope / Qwen | `DASHSCOPE_API_KEY` | https://bailian.console.aliyun.com/ | https://help.aliyun.com/zh/model-studio/ | Region and endpoint mode may differ between China and international accounts. |
| Cerebras | `CEREBRAS_API_KEY` | https://cloud.cerebras.ai/ | https://inference-docs.cerebras.ai/ | Verify current free-tier and model quota before use. |
| Cloudflare Workers AI | `CLOUDFLARE_API_TOKEN` plus `CLOUDFLARE_ACCOUNT_ID` | https://dash.cloudflare.com/profile/api-tokens | https://developers.cloudflare.com/workers-ai/ | Use a least-privilege token scoped to the required account and Workers AI resources. |
| Codestral | `CODESTRAL_API_KEY` | https://console.mistral.ai/ | https://docs.mistral.ai/ | Codestral may share or separate credentials depending on the current Mistral account configuration. |
| DeepSeek | `DEEPSEEK_API_KEY` | https://platform.deepseek.com/api_keys | https://api-docs.deepseek.com/ | Check account balance, quota, retention, and regional policy before production use. |
| Fireworks AI | `FIREWORKS_API_KEY` | https://app.fireworks.ai/settings/users/api-keys | https://docs.fireworks.ai/ | Restrict key access and configure spend controls where available. |
| GitHub Models | `GITHUB_MODELS_TOKEN` | https://github.com/settings/tokens | https://docs.github.com/en/github-models | Prefer a fine-grained token with only the permissions required by GitHub Models. |
| Google AI Studio / Gemini | `GEMINI_API_KEY` | https://aistudio.google.com/app/apikey | https://ai.google.dev/gemini-api/docs | Restrict the key by project and API where supported; review free-tier quotas. |
| Groq | `GROQ_API_KEY` | https://console.groq.com/keys | https://console.groq.com/docs/ | Verify current model availability and rate limits before adding to failover. |
| Kimi / Moonshot AI | `KIMI_API_KEY` | https://platform.moonshot.ai/console/api-keys | https://platform.moonshot.ai/docs/ | Endpoint and product availability may vary by account and region. |
| Mistral La Plateforme | `MISTRAL_API_KEY` | https://console.mistral.ai/api-keys/ | https://docs.mistral.ai/ | Apply usage limits and keep Codestral separation explicit if required. |
| NVIDIA NIM / API Catalog | `NVIDIA_NIM_API_KEY` | https://build.nvidia.com/ | https://docs.api.nvidia.com/ | Generate the key from the NVIDIA API Catalog. Free Endpoint access is evaluation-oriented and quota-bound. |
| OpenCode Zen | `OPENCODE_API_KEY` | https://opencode.ai/ | https://opencode.ai/docs/zen/ | Confirm the current account/key workflow in the official console before use. |
| OpenRouter | `OPENROUTER_API_KEY` | https://openrouter.ai/settings/keys | https://openrouter.ai/docs/ | Set provider routing, privacy, and budget controls explicitly. |
| OVHcloud AI Endpoints | `OVHCLOUD_API_KEY` | https://www.ovhcloud.com/manager/ | https://endpoints.ai.cloud.ovh.net/ | Endpoint and credential setup may depend on OVHcloud project and region. |
| SambaNova Cloud | `SAMBANOVA_API_KEY` | https://cloud.sambanova.ai/ | https://docs.sambanova.ai/ | Verify current free developer access and model-specific limits. |
| Scaleway Generative APIs | `SCALEWAY_API_KEY` | https://console.scaleway.com/iam/api-keys | https://www.scaleway.com/en/docs/generative-apis/ | Use a project-scoped IAM key and the correct regional endpoint. |
| Wafer | `WAFER_API_KEY` | https://wafer.ai/ | https://docs.wafer.ai/ | Confirm the official credential console and Messages-compatible endpoint before activation. |
| Z.ai | `ZAI_API_KEY` | https://open.bigmodel.cn/usercenter/apikeys | https://docs.z.ai/ | Product naming, region, and OpenAI/Anthropic compatibility may differ by account. |

## Local runtimes

The following local providers normally do not require a hosted API key unless the operator enables authentication:

| Provider | Environment variable | Default endpoint |
|---|---|---|
| LM Studio | none by default | `LM_STUDIO_BASE_URL=http://localhost:1234/v1` |
| llama.cpp server | none by default | `LLAMACPP_BASE_URL=http://localhost:8080/v1` |
| Ollama | none by default | `OLLAMA_BASE_URL=http://localhost:11434/v1` |

## Generate an A–Z placeholder file

Run:

```bash
./scripts/generate-provider-api-key-list.sh
```

The script reads `.env.example`, extracts credential variable names, sorts them A–Z, and writes placeholders to `API-KEY.txt`. It never copies populated values.

Example output:

```env
CEREBRAS_API_KEY=
CLOUDFLARE_API_TOKEN=
CODESTRAL_API_KEY=
DASHSCOPE_API_KEY=
DEEPSEEK_API_KEY=
FIREWORKS_API_KEY=
GEMINI_API_KEY=
GITHUB_MODELS_TOKEN=
GROQ_API_KEY=
KIMI_API_KEY=
MISTRAL_API_KEY=
NVIDIA_NIM_API_KEY=
OPENCODE_API_KEY=
OPENROUTER_API_KEY=
OVHCLOUD_API_KEY=
SAMBANOVA_API_KEY=
SCALEWAY_API_KEY=
WAFER_API_KEY=
ZAI_API_KEY=
```

`CLOUDFLARE_ACCOUNT_ID` is included separately because it is required configuration but is not a secret API key.

## Activation gate

A credential existing in `.env` does not authorize production use. Before enabling a provider, verify:

1. Exact API base URL and model ID.
2. Authentication format.
3. Streaming and tool-calling behavior.
4. Upload and multimodal support.
5. Quotas, billing, and spend limits.
6. Data retention, privacy, residency, and acceptable-use terms.
7. Retry/failover safety and provider-specific error semantics.
8. Secret storage, rotation, revocation, and audit ownership.
