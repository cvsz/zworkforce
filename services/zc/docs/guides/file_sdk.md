# Makefile for Qwen Code + OpenCode Provider SDKs

## Files

Place these files in the same directory:

```text
Makefile
scripts/zai-config-gen.py
.env
```

Keep `.env` outside Git.

## Install all SDKs

```bash
make bootstrap
make sdk-all
```

Python provider SDKs include OpenAI, Anthropic, Google GenAI, Groq, Together,
Hugging Face, and LiteLLM. Node packages include provider SDKs plus Vercel AI SDK
adapters used by OpenCode-compatible integrations.

## Inspect providers safely

```bash
make env-status
```

This prints only provider state and endpoint information, never secret values.

## Generate both configurations

Strict-free and local models:

```bash
make generate-all
```

Every account-accessible model:

```bash
make generate-all INCLUDE_ACCESSIBLE=1
```

Selected providers:

```bash
make generate-all \
  INCLUDE_ACCESSIBLE=1 \
  PROVIDERS=openrouter,nvidia-nim,groq,ollama,litellm
```

## Individual targets

```bash
make generate-qwen
make generate-opencode
make validate
make rotate
make rotate-previous
make status
make show-models
make show-opencode-models
```

## Custom paths

```bash
make generate-all \
  ENV_FILE=/secure/z-platform.env \
  QWEN_CONFIG=/tmp/qwen-settings.json \
  OPENCODE_CONFIG=/tmp/opencode.json
```

## Safety

`make check-env` fails if the selected `.env` is tracked by Git. Generated
configuration files reference environment variable names; they do not embed API
key values.
