# NVIDIA Free Endpoint Models

This document tracks NVIDIA API Catalog models that NVIDIA currently labels **Free Endpoint**. It is documentation only: no model is enabled automatically, no credential is committed, and no production traffic is authorized by this file.

## Source of truth

- Catalog: https://build.nvidia.com/models
- API documentation: https://docs.api.nvidia.com
- OpenAI-compatible base URL: `https://integrate.api.nvidia.com/v1`
- Credential variable: `NVIDIA_NIM_API_KEY`

The NVIDIA catalog reported **76 Free Endpoint models** on 2026-07-14. The catalog is dynamic: models can be added, removed, moved to partner endpoints, or marked for deprecation. Always re-check the official **Free Endpoint** filter before generating a production configuration.

`Free Endpoint` means NVIDIA currently exposes a hosted endpoint for evaluation under the applicable NVIDIA account, quota, credit, and terms. It does not mean unlimited, anonymous, or permanently free production inference.

## Recommended text, coding, reasoning, and agent models

| Catalog model | Publisher | Primary use | Z Platform recommendation |
|---|---|---|---|
| `glm-5.2` | Z.ai | agentic workflows, coding, long-horizon reasoning | candidate |
| `minimax-m3` | MiniMax | multimodal reasoning, coding, tool calling | candidate |
| `nemotron-3-ultra-550b-a55b` | NVIDIA | advanced agents, coding, planning, tool calling | candidate; high latency/cost risk |
| `step-3.7-flash` | StepFun | multimodal reasoning, agents, coding | candidate |
| `mistral-medium-3.5-128b` | Mistral AI | text, coding, agentic workloads | candidate |
| `deepseek-v4-flash` | DeepSeek AI | fast coding and agents | candidate |
| `deepseek-v4-pro` | DeepSeek AI | coding and long-context reasoning | candidate; high latency risk |
| `minimax-m2.7` | MiniMax | coding, reasoning, office workloads | candidate |
| `gemma-4-31b-it` | Google | reasoning, coding, fine-tuning | candidate |
| `mistral-small-4-119b-2603` | Mistral AI | instruction, reasoning, coding, multimodal input | candidate |
| `nemotron-3-super-120b-a12b` | NVIDIA | agents, coding, planning, tool calling | preferred NVIDIA balanced tier |
| `qwen3.5-122b-a10b` | Qwen | coding, reasoning, multimodal chat, tools | candidate |
| `qwen3.5-397b-a17b` | Qwen | vision, chat, RAG, agentic workloads | candidate; high latency risk |
| `step-3.5-flash` | StepFun | agentic reasoning | candidate |
| `nemotron-3-nano-30b-a3b` | NVIDIA | fast coding, reasoning, tools | preferred NVIDIA low-latency tier |
| `mistral-large-3-675b-instruct-2512` | Mistral AI | general chat, agents, instruction following | candidate; high latency risk |

## Multimodal and media models

| Catalog model | Capability | Z Platform status |
|---|---|---|
| `diffusiongemma-26b-a4b-it` | diffusion-language text generation | research candidate |
| `nemotron-3-nano-omni-30b-a3b-reasoning` | image, video, speech, and text reasoning | multimodal candidate |
| `cosmos3-nano` | physics-aware video generation | specialized; disabled by default |
| `cosmos3-nano-reasoner` | image/video physical-world reasoning | specialized; disabled by default |
| `cosmos-transfer2.5-2b` | controlled physical-world video generation | specialized; disabled by default |
| `synthetic-video-detector` | synthetic-video detection | media-safety candidate |
| `Active Speaker Detection` | speaker detection and tracking in video | media-analysis candidate |
| `ising-calibration-1-35b-a3b` | quantum calibration chart understanding | specialized; disabled by default |
| `nemotron-voicechat` | voice conversation | voice candidate; separate streaming contract required |
| `riva-translate-4b-instruct-v1_1` | multilingual translation | translation candidate |

## Safety and privacy models

| Catalog model | Capability | Status |
|---|---|---|
| `nemotron-3.5-content-safety` | multilingual, multimodal safety classification | preferred safety candidate |
| `gliner-pii` | personally identifiable information detection | preferred redaction candidate |
| `nemotron-3-content-safety` | content safety | **do not newly adopt**; catalog showed a deprecation notice |
| `nemotron-content-safety-reasoning-4b` | policy-aware safety reasoning | **do not newly adopt**; catalog showed a deprecation notice |

## Suggested initial model set

Use this small set for controlled staging evaluation before considering the broader catalog:

```text
nvidia/nemotron-3-nano-30b-a3b
nvidia/nemotron-3-super-120b-a12b
nvidia/nemotron-3.5-content-safety
nvidia/gliner-pii
qwen/qwen3.5-122b-a10b
mistralai/mistral-small-4-119b-2603
```

The exact model IDs accepted by `GET /v1/models` are authoritative. Catalog slugs and runtime model IDs may differ, so do not copy these recommendation labels into production routing without querying the authenticated API.

## Verification before enablement

For every selected model, record:

1. Exact ID returned by `GET https://integrate.api.nvidia.com/v1/models`.
2. Chat-completions, embeddings, image, audio, video, or provider-specific protocol.
3. Streaming behavior and termination semantics.
4. Tool/function-calling support.
5. Context and output limits.
6. Rate-limit and quota behavior.
7. File or multimodal payload constraints.
8. Retry safety for HTTP 429 and 5xx responses.
9. Content retention, licensing, and acceptable-use requirements.
10. Deprecation status and replacement model.

## Example discovery command

Run locally with a populated secret. Do not paste the output if it contains account-specific information.

```bash
curl -fsS https://integrate.api.nvidia.com/v1/models \
  -H "Authorization: Bearer ${NVIDIA_NIM_API_KEY}" \
  -H 'Accept: application/json' |
  jq -r '.data[]?.id' |
  sort
```

This command discovers model IDs available to the authenticated account. It does not by itself prove that every returned model is a current NVIDIA **Free Endpoint**; cross-check the catalog filter and account quota before enablement.
