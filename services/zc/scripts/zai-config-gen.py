#!/usr/bin/env python3
"""
qwen_config_generator.py

Generate and maintain a multi-provider Qwen Code configuration from environment variables and live model catalogs.

Security:
- Reads credentials from environment variables or a local .env file.
- Never writes credential values into settings.json.
- Writes only envKey references.
- Does not print secrets.

Supported catalog adapters:
- OpenRouter (strict zero-price filtering)
- NVIDIA NIM
- Groq
- Together AI
- DeepSeek
- Hugging Face Router
- OpenAI
- Ollama
- LiteLLM
- Anthropic
- Google Gemini

Qwen Code output schema:
  modelProviders.<authType>[]
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SETTINGS_PATH = Path.home() / ".qwen" / "settings.json"
DEFAULT_STATE_PATH = Path.home() / ".qwen" / "model-rotation-state.json"
DEFAULT_OPENCODE_SETTINGS_PATH = Path.home() / ".config" / "opencode" / "opencode.json"
DEFAULT_TIMEOUT = 30

EXCLUDED_MODEL_FRAGMENTS = (
    "embed",
    "embedding",
    "rerank",
    "reranker",
    "moderation",
    "whisper",
    "transcribe",
    "speech",
    "tts",
    "text-to-image",
    "image-generation",
    "reward",
)

CODING_HINTS = (
    "coder",
    "code",
    "devstral",
    "codestral",
    "qwen",
    "deepseek",
    "glm",
    "gpt-oss",
    "nemotron",
    "llama",
    "mistral",
    "kimi",
)

FREE_ENV_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    auth_type: str
    protocol: str
    base_url: str
    env_key: str
    catalog_kind: str = "openai"
    strict_free: bool = False
    local: bool = False
    enabled_env: str | None = None


PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        name="OpenRouter",
        auth_type="openai",
        protocol="openai",
        base_url="https://openrouter.ai/api/v1",
        env_key="OPENROUTER_API_KEY",
        strict_free=True,
    ),
    ProviderSpec(
        name="NVIDIA NIM",
        auth_type="openai",
        protocol="openai",
        base_url="https://integrate.api.nvidia.com/v1",
        env_key="NVIDIA_NIM_API_KEY",
    ),
    ProviderSpec(
        name="Groq",
        auth_type="openai",
        protocol="openai",
        base_url="https://api.groq.com/openai/v1",
        env_key="GROQ_API_KEY",
    ),
    ProviderSpec(
        name="Together AI",
        auth_type="openai",
        protocol="openai",
        base_url="https://api.together.xyz/v1",
        env_key="TOGETHER_API_KEY",
    ),
    ProviderSpec(
        name="DeepSeek",
        auth_type="openai",
        protocol="openai",
        base_url="https://api.deepseek.com/v1",
        env_key="DEEPSEEK_API_KEY",
    ),
    ProviderSpec(
        name="Hugging Face Router",
        auth_type="openai",
        protocol="openai",
        base_url="https://router.huggingface.co/v1",
        env_key="HF_TOKEN_API_KEY",
    ),
    ProviderSpec(
        name="OpenAI",
        auth_type="openai",
        protocol="openai",
        base_url="https://api.openai.com/v1",
        env_key="OPENAI_API_KEY",
    ),
    ProviderSpec(
        name="Ollama",
        auth_type="openai",
        protocol="openai",
        base_url="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}/v1",
        env_key="OLLAMA_API_KEY",
        local=True,
    ),
    ProviderSpec(
        name="LiteLLM",
        auth_type="openai",
        protocol="openai",
        base_url="${LITELLM_BASE_URL:-http://127.0.0.1:4000}/v1",
        env_key="LITELLM_MASTER_KEY",
        local=True,
    ),
    ProviderSpec(
        name="Anthropic",
        auth_type="anthropic",
        protocol="anthropic",
        base_url="https://api.anthropic.com",
        env_key="ANTHROPIC_API_KEY",
        catalog_kind="anthropic",
    ),
    ProviderSpec(
        name="Google Gemini",
        auth_type="gemini",
        protocol="gemini",
        base_url="https://generativelanguage.googleapis.com",
        env_key="GEMINI_API_KEY",
        catalog_kind="gemini",
    ),
    ProviderSpec(
        name="Mistral AI",
        auth_type="openai",
        protocol="openai",
        base_url="https://api.mistral.ai/v1",
        env_key="MISTRAL_API_KEY",
    ),
    ProviderSpec(
        name="Perplexity",
        auth_type="openai",
        protocol="openai",
        base_url="https://api.perplexity.ai",
        env_key="PERPLEXITY_API_KEY",
    ),
    ProviderSpec(
        name="Fireworks AI",
        auth_type="openai",
        protocol="openai",
        base_url="https://api.fireworks.ai/inference/v1",
        env_key="FIREWORKS_API_KEY",
    ),
    ProviderSpec(
        name="Anyscale",
        auth_type="openai",
        protocol="openai",
        base_url="https://api.endpoints.anyscale.com/v1",
        env_key="ANYSCALE_API_KEY",
    ),
    ProviderSpec(
        name="OctoAI",
        auth_type="openai",
        protocol="openai",
        base_url="https://text.octoai.run/v1",
        env_key="OCTOAI_API_KEY",
    ),
    ProviderSpec(
        name="Cerebras",
        auth_type="openai",
        protocol="openai",
        base_url="https://api.cerebras.ai/v1",
        env_key="CEREBRAS_API_KEY",
    ),
    ProviderSpec(
        name="xAI",
        auth_type="openai",
        protocol="openai",
        base_url="https://api.x.ai/v1",
        env_key="XAI_API_KEY",
    ),
    ProviderSpec(
        name="Alibaba DashScope",
        auth_type="openai",
        protocol="openai",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        env_key="DASHSCOPE_API_KEY",
    ),
    ProviderSpec(
        name="LM Studio",
        auth_type="openai",
        protocol="openai",
        base_url="${LMSTUDIO_BASE_URL:-http://127.0.0.1:1234}/v1",
        env_key="LMSTUDIO_API_KEY",
        local=True,
    ),
    ProviderSpec(
        name="Zhipu AI",
        auth_type="openai",
        protocol="openai",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        env_key="ZHIPU_API_KEY",
    ),
)


def eprint(message: str) -> None:
    sys.stderr.write(message.rstrip() + "\n")


def parse_env_file(path: Path) -> dict[str, str]:
    """
    Minimal .env parser.

    Existing process environment wins over file values.
    Shell expansions and command substitutions are intentionally unsupported.
    """
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8", errors="replace").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            eprint(f"Warning: ignoring malformed .env line {line_number}")
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            eprint(f"Warning: ignoring invalid variable name at line {line_number}")
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        values[key] = value

    return values


def merged_environment(env_file: Path | None) -> dict[str, str]:
    merged = dict(os.environ)
    if env_file is not None:
        for key, value in parse_env_file(env_file).items():
            merged.setdefault(key, value)

    # Compatibility aliases observed in existing configurations.
    if "NVIDIA_NIM_API_KEY" not in merged:
        alias = merged.get(
            "QWEN_CUSTOM_API_KEY_OPENAI_HTTPS_INTEGRATE_API_NVIDIA_COM_V1_D384067BF088"
        )
        if alias:
            merged["NVIDIA_NIM_API_KEY"] = alias

    if "GEMINI_API_KEY" not in merged:
        alias = merged.get(
            "QWEN_CUSTOM_API_KEY_GEMINI_HTTPS_GENERATIVELANGUAGE_GOOGLEAPIS_COM_2204C1361727"
        )
        if alias:
            merged["GEMINI_API_KEY"] = alias

    if "XAI_API_KEY" not in merged and merged.get("XAI_API_KET"):
        merged["XAI_API_KEY"] = merged["XAI_API_KET"]

    return merged


_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def expand_env_template(value: str, env: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        default = match.group(2) or ""
        return env.get(key) or default

    return _VAR_PATTERN.sub(replace, value)


def request_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "qwen-code-config-generator/4.0",
    }
    if headers:
        request_headers.update(headers)

    request = urllib.request.Request(url, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc
    except TimeoutError as exc:
        raise RuntimeError("request timed out") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("unexpected non-object response")
    return payload


def zero_price(value: Any, *, missing_is_zero: bool = False) -> bool:
    if value is None:
        return missing_is_zero
    try:
        return float(str(value)) == 0.0
    except (TypeError, ValueError):
        return False


def is_text_model(item: dict[str, Any]) -> bool:
    model_id = str(item.get("id") or item.get("name") or "").lower()
    if not model_id:
        return False
    if any(fragment in model_id for fragment in EXCLUDED_MODEL_FRAGMENTS):
        return False

    architecture = item.get("architecture")
    if isinstance(architecture, dict):
        output_modalities = architecture.get("output_modalities")
        if isinstance(output_modalities, list) and output_modalities:
            return "text" in output_modalities

    capabilities = item.get("capabilities")
    if isinstance(capabilities, dict):
        output_modalities = capabilities.get("output_modalities")
        if isinstance(output_modalities, list) and output_modalities:
            return "text" in output_modalities

    return True


def is_openrouter_free(item: dict[str, Any]) -> bool:
    model_id = str(item.get("id", ""))
    if model_id == "openrouter/free" or model_id.endswith(":free"):
        return True

    pricing = item.get("pricing")
    if not isinstance(pricing, dict):
        return False

    return (
        zero_price(pricing.get("prompt"))
        and zero_price(pricing.get("completion"))
        and zero_price(pricing.get("request"), missing_is_zero=True)
    )


def model_context_length(item: dict[str, Any]) -> int | None:
    for field in ("context_length", "context_window", "max_input_tokens"):
        value = item.get(field)
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.isdigit():
            parsed = int(value)
            if parsed > 0:
                return parsed
    return None


def normalize_openai_models(
    payload: dict[str, Any],
    spec: ProviderSpec,
    *,
    include_accessible: bool,
) -> list[dict[str, Any]]:
    data = payload.get("data", [])
    if not isinstance(data, list):
        raise RuntimeError("catalog has no data array")

    models: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict) or not is_text_model(item):
            continue

        model_id = item.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            continue

        if spec.strict_free and not is_openrouter_free(item):
            continue
        if not spec.strict_free and not spec.local and not include_accessible:
            continue

        context_length = model_context_length(item)
        architecture = item.get("architecture", {})
        input_modalities: list[str] = []
        if isinstance(architecture, dict):
            raw_modalities = architecture.get("input_modalities", [])
            if isinstance(raw_modalities, list):
                input_modalities = [
                    value for value in raw_modalities if isinstance(value, str)
                ]

        models.append(
            {
                "id": model_id.strip(),
                "name": str(item.get("name") or model_id),
                "context_length": context_length,
                "input_modalities": input_modalities,
                "source": spec.name,
                "free_class": (
                    "strict-free"
                    if spec.strict_free
                    else "local-no-api-charge"
                    if spec.local
                    else "accessible-unverified"
                ),
            }
        )

    if spec.name == "OpenRouter" and not any(
        item["id"] == "openrouter/free" for item in models
    ):
        models.insert(
            0,
            {
                "id": "openrouter/free",
                "name": "OpenRouter Free Router",
                "context_length": 200000,
                "input_modalities": ["text"],
                "source": spec.name,
                "free_class": "strict-free",
            },
        )

    return models


def fetch_openai_catalog(
    spec: ProviderSpec,
    env: dict[str, str],
    *,
    timeout: int,
    include_accessible: bool,
) -> list[dict[str, Any]]:
    base_url = expand_env_template(spec.base_url, env).rstrip("/")
    api_key = env.get(spec.env_key, "")

    if not api_key and not spec.local:
        return []
    if spec.local and not base_url:
        return []

    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = request_json(f"{base_url}/models", headers=headers, timeout=timeout)
    return normalize_openai_models(
        payload,
        spec,
        include_accessible=include_accessible,
    )


def fetch_anthropic_catalog(
    spec: ProviderSpec,
    env: dict[str, str],
    *,
    timeout: int,
    include_accessible: bool,
) -> list[dict[str, Any]]:
    if not include_accessible:
        return []

    api_key = env.get(spec.env_key, "")
    if not api_key:
        return []

    payload = request_json(
        f"{spec.base_url.rstrip('/')}/v1/models",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        timeout=timeout,
    )
    data = payload.get("data", [])
    if not isinstance(data, list):
        raise RuntimeError("catalog has no data array")

    result: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if isinstance(model_id, str) and model_id:
            result.append(
                {
                    "id": model_id,
                    "name": str(item.get("display_name") or model_id),
                    "context_length": None,
                    "input_modalities": ["text"],
                    "source": spec.name,
                    "free_class": "accessible-unverified",
                }
            )
    return result


def fetch_gemini_catalog(
    spec: ProviderSpec,
    env: dict[str, str],
    *,
    timeout: int,
    include_accessible: bool,
) -> list[dict[str, Any]]:
    if not include_accessible:
        return []

    api_key = env.get(spec.env_key, "")
    if not api_key:
        return []

    query = urllib.parse.urlencode({"key": api_key, "pageSize": 1000})
    payload = request_json(
        f"{spec.base_url.rstrip('/')}/v1beta/models?{query}",
        timeout=timeout,
    )
    data = payload.get("models", [])
    if not isinstance(data, list):
        raise RuntimeError("catalog has no models array")

    result: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        methods = item.get("supportedGenerationMethods", [])
        if isinstance(methods, list) and "generateContent" not in methods:
            continue

        raw_name = item.get("name")
        if not isinstance(raw_name, str) or not raw_name:
            continue
        model_id = raw_name.removeprefix("models/")

        result.append(
            {
                "id": model_id,
                "name": str(item.get("displayName") or model_id),
                "context_length": item.get("inputTokenLimit"),
                "input_modalities": ["text"],
                "source": spec.name,
                "free_class": "accessible-unverified",
            }
        )
    return result


def fetch_provider_catalog(
    spec: ProviderSpec,
    env: dict[str, str],
    *,
    timeout: int,
    include_accessible: bool,
) -> list[dict[str, Any]]:
    if spec.enabled_env:
        enabled = env.get(spec.enabled_env, "").lower() in FREE_ENV_VALUES
        if not enabled:
            return []

    if spec.catalog_kind == "openai":
        return fetch_openai_catalog(
            spec,
            env,
            timeout=timeout,
            include_accessible=include_accessible,
        )
    if spec.catalog_kind == "anthropic":
        return fetch_anthropic_catalog(
            spec,
            env,
            timeout=timeout,
            include_accessible=include_accessible,
        )
    if spec.catalog_kind == "gemini":
        return fetch_gemini_catalog(
            spec,
            env,
            timeout=timeout,
            include_accessible=include_accessible,
        )
    raise RuntimeError(f"unsupported catalog kind: {spec.catalog_kind}")


def model_score(model: dict[str, Any]) -> tuple[int, int, str]:
    model_id = str(model["id"]).lower()
    coding_score = sum(
        1 for index, hint in enumerate(CODING_HINTS)
        if hint in model_id
    )
    context_length = model.get("context_length")
    context_score = context_length if isinstance(context_length, int) else 0
    return (-coding_score, -context_score, model_id)


def generation_config(model: dict[str, Any]) -> dict[str, Any]:
    config: dict[str, Any] = {
        "timeout": 120000,
        "maxRetries": 3,
        "samplingParams": {
            "temperature": 0.2,
            "top_p": 0.9,
            "max_tokens": 8192,
        },
        "modalities": {
            "text": True,
        },
    }

    context_length = model.get("context_length")
    if isinstance(context_length, int) and context_length > 0:
        config["contextWindowSize"] = context_length

    modalities = model.get("input_modalities", [])
    if isinstance(modalities, list):
        for modality in modalities:
            if modality in {"image", "audio", "video", "pdf"}:
                config["modalities"][modality] = True

    return config


def qwen_model_entry(
    spec: ProviderSpec,
    model: dict[str, Any],
    env: dict[str, str],
) -> dict[str, Any]:
    base_url = expand_env_template(spec.base_url, env).rstrip("/")
    entry: dict[str, Any] = {
        "id": model["id"],
        "name": f"{spec.name} · {model['name']}",
        "description": (
            f"{model['free_class']}; catalog refreshed automatically. "
            "Availability, quotas, and pricing can change."
        ),
        "envKey": spec.env_key,
        "generationConfig": generation_config(model),
    }

    # Qwen's Gemini and Anthropic SDKs use their native service endpoints.
    # baseUrl is omitted for the official native endpoints to preserve SDK defaults.
    if spec.auth_type == "openai":
        entry["baseUrl"] = base_url

    return entry


def collect_catalog(
    env: dict[str, str],
    *,
    timeout: int,
    include_accessible: bool,
    provider_filter: set[str] | None,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    rotation: list[dict[str, Any]] = []

    for spec in PROVIDERS:
        normalized_name = spec.name.lower().replace(" ", "-")
        if provider_filter and normalized_name not in provider_filter:
            continue

        try:
            models = fetch_provider_catalog(
                spec,
                env,
                timeout=timeout,
                include_accessible=include_accessible,
            )
        except RuntimeError as exc:
            eprint(f"{spec.name}: skipped ({exc})")
            continue

        if not models:
            continue

        models = sorted(models, key=model_score)
        group = groups.setdefault(spec.auth_type, [])

        for model in models:
            entry = qwen_model_entry(spec, model, env)
            group.append(entry)
            rotation.append(
                {
                    "auth_type": spec.auth_type,
                    "id": model["id"],
                    "base_url": entry.get("baseUrl"),
                    "provider": spec.name,
                    "free_class": model["free_class"],
                }
            )

        print(f"{spec.name}: {len(models)} model(s)")

    return groups, rotation



def provider_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "provider"


def provider_spec_by_name(name: str) -> ProviderSpec:
    for spec in PROVIDERS:
        if spec.name == name:
            return spec
    raise RuntimeError(f"unknown provider: {name}")


def build_opencode_config(
    groups: dict[str, list[dict[str, Any]]],
    rotation: list[dict[str, Any]],
    env: dict[str, str],
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = copy.deepcopy(existing or {})
    config["$schema"] = "https://opencode.ai/config.json"
    providers: dict[str, dict[str, Any]] = {}

    for models in groups.values():
        if not isinstance(models, list):
            continue
        for entry in models:
            if not isinstance(entry, dict):
                continue
            display_name = str(entry.get("name", ""))
            provider_name = display_name.split(" · ", 1)[0].strip()
            if not provider_name:
                continue
            try:
                spec = provider_spec_by_name(provider_name)
            except RuntimeError:
                continue
            slug = provider_slug(spec.name)
            provider = providers.setdefault(slug, {"name": spec.name, "models": {}})
            if spec.protocol == "openai":
                provider["npm"] = "@ai-sdk/openai-compatible"
                provider["options"] = {
                    "baseURL": expand_env_template(spec.base_url, env).rstrip("/"),
                    "apiKey": f"{{env:{spec.env_key}}}",
                }
            elif spec.protocol == "anthropic":
                provider["npm"] = "@ai-sdk/anthropic"
                provider["options"] = {"apiKey": f"{{env:{spec.env_key}}}"}
            elif spec.protocol == "gemini":
                provider["npm"] = "@ai-sdk/google"
                provider["options"] = {"apiKey": f"{{env:{spec.env_key}}}"}
            else:
                continue
            model_id = entry.get("id")
            if not isinstance(model_id, str) or not model_id:
                continue
            model_config: dict[str, Any] = {"name": display_name.split(" · ", 1)[-1] or model_id}
            generation = entry.get("generationConfig", {})
            if isinstance(generation, dict):
                context = generation.get("contextWindowSize")
                sampling = generation.get("samplingParams", {})
                output = sampling.get("max_tokens") if isinstance(sampling, dict) else None
                limits: dict[str, int] = {}
                if isinstance(context, int) and context > 0:
                    limits["context"] = context
                if isinstance(output, int) and output > 0:
                    limits["output"] = output
                if limits:
                    model_config["limit"] = limits
            provider["models"][model_id] = model_config

    config["provider"] = providers
    if rotation:
        selected = rotation[0]
        config["model"] = f"{provider_slug(str(selected['provider']))}/{selected['id']}"
        small = next((item for item in reversed(rotation) if item["provider"] == selected["provider"]), selected)
        config["small_model"] = f"{provider_slug(str(small['provider']))}/{small['id']}"
    return config


def validate_opencode_config(path: Path) -> list[str]:
    errors: list[str] = []
    config = load_json(path, {})
    if config.get("$schema") != "https://opencode.ai/config.json":
        errors.append("missing or invalid $schema")
    providers = config.get("provider")
    if not isinstance(providers, dict) or not providers:
        errors.append("provider is missing or empty")
        return errors
    for provider_id, provider in providers.items():
        if not isinstance(provider, dict):
            errors.append(f"provider.{provider_id} must be an object")
            continue
        models = provider.get("models")
        if not isinstance(models, dict) or not models:
            errors.append(f"provider.{provider_id}.models is missing or empty")
        options = provider.get("options", {})
        if isinstance(options, dict) and "apiKey" in options:
            api_key = options["apiKey"]
            if not (isinstance(api_key, str) and api_key.startswith("{env:") and api_key.endswith("}")):
                errors.append(f"provider.{provider_id}.options.apiKey must use {{env:VAR}}")
    model = config.get("model")
    if not isinstance(model, str) or "/" not in model:
        errors.append("model must be provider_id/model_id")
    return errors


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return copy.deepcopy(default)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return payload


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        handle.write(serialized)
        handle.flush()
        os.fsync(handle.fileno())

    os.replace(temp_path, path)


def backup_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.{timestamp}.bak")
    shutil.copy2(path, backup)
    return backup


def generate_command(args: argparse.Namespace, env: dict[str, str]) -> int:
    provider_filter = (
        {name.strip().lower() for name in args.providers.split(",") if name.strip()}
        if args.providers
        else None
    )

    groups, rotation = collect_catalog(
        env,
        timeout=args.timeout,
        include_accessible=args.include_accessible,
        provider_filter=provider_filter,
    )

    if not rotation:
        eprint(
            "No eligible models found. Set provider keys, start local endpoints, "
            "or pass --include-accessible."
        )
        return 2

    settings = load_json(args.settings, {})
    state = load_json(args.state, {"index": -1})

    settings["modelProviders"] = groups
    settings.setdefault("security", {}).setdefault("auth", {})
    settings.setdefault("model", {})
    settings.setdefault("general", {})

    current_name = settings["model"].get("name")
    current_auth = settings["security"]["auth"].get("selectedType")

    current_index = next(
        (
            index
            for index, item in enumerate(rotation)
            if item["id"] == current_name and item["auth_type"] == current_auth
        ),
        -1,
    )

    if current_index < 0:
        current_index = 0
        selected = rotation[0]
        settings["model"]["name"] = selected["id"]
        settings["security"]["auth"]["selectedType"] = selected["auth_type"]

    settings["model"].setdefault("maxToolCalls", 200)
    settings["general"].setdefault("enableAutoUpdate", True)
    settings["general"].setdefault("showSessionRecap", True)

    state.update(
        {
            "schemaVersion": "1.0.0",
            "index": current_index,
            "rotation": rotation,
            "updatedAt": int(time.time()),
        }
    )

    opencode_config = build_opencode_config(
        groups, rotation, env,
        load_json(args.opencode_settings, {}) if args.opencode_settings.exists() else {},
    )

    if not args.dry_run:
        if args.target in {"both", "qwen"}:
            backup = backup_file(args.settings)
            atomic_write_json(args.settings, settings)
            atomic_write_json(args.state, state)
            if backup:
                print(f"Qwen backup: {backup}")
            print(f"Qwen settings: {args.settings}")
            print(f"Rotation state: {args.state}")
        if args.target in {"both", "opencode"}:
            backup = backup_file(args.opencode_settings)
            atomic_write_json(args.opencode_settings, opencode_config)
            if backup:
                print(f"OpenCode backup: {backup}")
            print(f"OpenCode settings: {args.opencode_settings}")
    else:
        payload: dict[str, Any] = {}
        if args.target in {"both", "qwen"}:
            payload["qwen"] = settings
        if args.target in {"both", "opencode"}:
            payload["opencode"] = opencode_config
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    print(f"Eligible models: {len(rotation)}")
    print(f"Qwen active: {settings['security']['auth']['selectedType']} / {settings['model']['name']}")
    print(f"OpenCode active: {opencode_config.get('model', '<unset>')}")
    return 0


def rotate_command(args: argparse.Namespace) -> int:
    settings = load_json(args.settings, {})
    state = load_json(args.state, {})

    rotation = state.get("rotation")
    if not isinstance(rotation, list) or not rotation:
        eprint("Rotation state is empty. Run generate first.")
        return 2

    step = args.step % len(rotation)
    current_index = state.get("index", -1)
    if not isinstance(current_index, int):
        current_index = -1

    new_index = (current_index + step) % len(rotation)
    selected = rotation[new_index]

    if not isinstance(selected, dict):
        eprint("Rotation state is invalid.")
        return 2

    settings.setdefault("security", {}).setdefault("auth", {})
    settings.setdefault("model", {})
    settings["security"]["auth"]["selectedType"] = selected["auth_type"]
    settings["model"]["name"] = selected["id"]

    state["index"] = new_index
    state["lastRotatedAt"] = int(time.time())

    if not args.dry_run:
        backup = backup_file(args.settings)
        atomic_write_json(args.settings, settings)
        atomic_write_json(args.state, state)
        if backup:
            print(f"Backup: {backup}")
    else:
        print(json.dumps(settings, indent=2, ensure_ascii=False))

    print(
        f"Rotated to [{new_index + 1}/{len(rotation)}] "
        f"{selected['provider']} · {selected['id']} "
        f"({selected['free_class']})"
    )
    return 0



def env_status_command(args: argparse.Namespace, env: dict[str, str]) -> int:
    """Show which provider variables are available without printing secrets."""
    rows: list[tuple[str, str, str]] = []

    for spec in PROVIDERS:
        base_url = expand_env_template(spec.base_url, env)
        key_present = bool(env.get(spec.env_key, "").strip())
        rows.append(
            (
                spec.name,
                "configured" if key_present else "local/no-key" if spec.local else "missing",
                base_url,
            )
        )

    width = max(len(row[0]) for row in rows)
    for provider, state, base_url in rows:
        print(f"{provider:<{width}}  {state:<12}  {base_url}")

    return 0



def validate_command(args: argparse.Namespace) -> int:
    settings = load_json(args.settings, {})
    providers = settings.get("modelProviders")
    if not isinstance(providers, dict) or not providers:
        eprint("Invalid configuration: modelProviders is missing or empty.")
        return 2

    errors: list[str] = []
    model_count = 0

    for auth_type, group in providers.items():
        if not isinstance(group, dict):
            errors.append(f"{auth_type}: provider group must be an object")
            continue

        protocol = group.get("protocol")
        models = group.get("models")
        if not isinstance(protocol, str) or not protocol:
            errors.append(f"{auth_type}: protocol is missing")
        if not isinstance(models, list) or not models:
            errors.append(f"{auth_type}: models is missing or empty")
            continue

        for index, model in enumerate(models):
            model_count += 1
            if not isinstance(model, dict):
                errors.append(f"{auth_type}.models[{index}]: must be an object")
                continue
            for required in ("id", "name", "envKey"):
                if not isinstance(model.get(required), str) or not model[required]:
                    errors.append(
                        f"{auth_type}.models[{index}]: {required} is missing"
                    )
            if auth_type == "openai":
                base_url = model.get("baseUrl")
                if not isinstance(base_url, str) or not base_url:
                    errors.append(
                        f"{auth_type}.models[{index}]: baseUrl is required"
                    )

    selected_type = (
        settings.get("security", {})
        .get("auth", {})
        .get("selectedType")
    )
    selected_model = settings.get("model", {}).get("name")

    if not isinstance(selected_type, str) or selected_type not in providers:
        errors.append("security.auth.selectedType does not match a provider group")
    elif isinstance(selected_model, str):
        models = providers[selected_type].get("models", [])
        if not any(
            isinstance(model, dict) and model.get("id") == selected_model
            for model in models
        ):
            errors.append("model.name is not present in the selected provider group")
    else:
        errors.append("model.name is missing")

    if errors:
        for error in errors:
            eprint(f"Validation error: {error}")
        return 2

    opencode_errors: list[str] = []
    if args.opencode_settings.exists():
        opencode_errors = validate_opencode_config(args.opencode_settings)
    if opencode_errors:
        for error in opencode_errors:
            eprint(f"OpenCode validation error: {error}")
        return 2
    print(f"Valid Qwen Code configuration: {args.settings}")
    print(f"Provider groups: {len(providers)}")
    print(f"Models: {model_count}")
    print(f"Selected: {selected_type} / {selected_model}")
    if args.opencode_settings.exists():
        print(f"Valid OpenCode configuration: {args.opencode_settings}")
    return 0


def status_command(args: argparse.Namespace) -> int:
    settings = load_json(args.settings, {})
    state = load_json(args.state, {})

    auth_type = (
        settings.get("security", {})
        .get("auth", {})
        .get("selectedType", "<unset>")
    )
    model = settings.get("model", {}).get("name", "<unset>")
    rotation = state.get("rotation", [])
    index = state.get("index", -1)

    print(f"Settings: {args.settings}")
    print(f"State: {args.state}")
    print(f"Selected auth type: {auth_type}")
    print(f"Selected model: {model}")
    print(f"Rotation entries: {len(rotation) if isinstance(rotation, list) else 0}")
    print(f"Rotation index: {index}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate, refresh, validate, inspect, and rotate Qwen Code model provider configuration safely."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Optional local .env file. Existing process environment wins.",
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=DEFAULT_SETTINGS_PATH,
        help=f"Qwen settings path (default: {DEFAULT_SETTINGS_PATH})",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_STATE_PATH,
        help=f"Rotation state path (default: {DEFAULT_STATE_PATH})",
    )
    parser.add_argument(
        "--opencode-settings",
        type=Path,
        default=DEFAULT_OPENCODE_SETTINGS_PATH,
        help=f"OpenCode config path (default: {DEFAULT_OPENCODE_SETTINGS_PATH})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="Catalog request timeout in seconds.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser(
        "generate",
        aliases=["refresh"],
        help="Load environment, fetch catalogs, and generate modelProviders.",
    )
    generate.add_argument(
        "--include-accessible",
        action="store_true",
        help=(
            "Include account-accessible cloud models whose zero-cost status "
            "cannot be proven from the catalog. Without this flag, only "
            "strict-free OpenRouter and reachable local models are included."
        ),
    )
    generate.add_argument(
        "--providers",
        default="",
        help=(
            "Comma-separated provider slugs, e.g. "
            "openrouter,nvidia-nim,ollama,litellm."
        ),
    )
    generate.add_argument(
        "--target",
        choices=("both", "qwen", "opencode"),
        default="both",
        help="Configuration target to generate (default: both).",
    )
    generate.add_argument("--dry-run", action="store_true")

    rotate = subparsers.add_parser(
        "rotate",
        help="Select the next model from the saved rotation list.",
    )
    rotate.add_argument(
        "--step",
        type=int,
        default=1,
        help="Number of positions to rotate (default: 1).",
    )
    rotate.add_argument("--dry-run", action="store_true")

    subparsers.add_parser(
        "env-status",
        help="Show configured provider variables without revealing secret values.",
    )
    subparsers.add_parser(
        "validate",
        help="Validate the generated Qwen Code settings structure.",
    )
    subparsers.add_parser("status", help="Show current rotation state.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    env = merged_environment(args.env_file)

    try:
        if args.command in {"generate", "refresh"}:
            return generate_command(args, env)
        if args.command == "rotate":
            return rotate_command(args)
        if args.command == "env-status":
            return env_status_command(args, env)
        if args.command == "validate":
            return validate_command(args)
        if args.command == "status":
            return status_command(args)
    except RuntimeError as exc:
        eprint(f"Error: {exc}")
        return 1
    except KeyboardInterrupt:
        eprint("Interrupted.")
        return 130

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
