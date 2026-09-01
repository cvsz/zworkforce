"""TradingAgents model catalog integration for ztrader.

Exposes the full provider and model catalog from TradingAgents so ztrader
users can select LLM providers and models for trading analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Core provider types (native APIs)
CORE_PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "models": ["gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.3", "gpt-5.2"],
        "env_key": "OPENAI_API_KEY",
        "type": "native",
    },
    "anthropic": {
        "name": "Anthropic",
        "models": ["claude-sonnet-4-6", "claude-haiku-4-5", "claude-opus-4-5"],
        "env_key": "ANTHROPIC_API_KEY",
        "type": "native",
    },
    "google": {
        "name": "Google Gemini",
        "models": ["gemini-3.1-pro", "gemini-3.1-flash", "gemini-3.0-pro"],
        "env_key": "GOOGLE_API_KEY",
        "type": "native",
    },
    "azure": {
        "name": "Azure OpenAI",
        "models": ["gpt-5.5", "gpt-5.4"],
        "env_key": "AZURE_OPENAI_API_KEY",
        "type": "native",
    },
    "bedrock": {
        "name": "AWS Bedrock",
        "models": ["claude-sonnet-4-6", "claude-haiku-4-5"],
        "env_key": "AWS_ACCESS_KEY_ID",
        "type": "native",
    },
}

# OpenAI-compatible providers
OPENAI_COMPATIBLE_PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "env_key": "DEEPSEEK_API_KEY",
        "type": "openai-compatible",
    },
    "qwen": {
        "name": "Qwen (Alibaba)",
        "models": ["qwen3.7-max", "qwen3.7-plus", "qwen3.6-max"],
        "env_key": "QWEN_API_KEY",
        "type": "openai-compatible",
    },
    "groq": {
        "name": "Groq",
        "models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "qwen/qwen3.6-27b",
            "groq/compound",
            "groq/compound-mini",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "allam-2-7b",
            "meta-llama/llama-prompt-guard-2-86m",
        ],
        "env_key": "GROQ_API_KEY",
        "type": "openai-compatible",
    },
    "mistral": {
        "name": "Mistral",
        "models": ["mistral-large-3.1", "mistral-small-3.1"],
        "env_key": "MISTRAL_API_KEY",
        "type": "openai-compatible",
    },
    "ollama": {
        "name": "Ollama (Local)",
        "models": ["custom"],
        "env_key": None,
        "type": "openai-compatible",
        "note": "Requires OLLAMA_BASE_URL env var",
    },
    "openrouter": {
        "name": "OpenRouter",
        "models": ["openrouter/auto"],
        "env_key": "OPENROUTER_API_KEY",
        "type": "openai-compatible",
    },
}


@dataclass
class ProviderInfo:
    """Information about an LLM provider."""
    key: str
    name: str
    models: list[str]
    env_key: str | None
    provider_type: str
    configured: bool = False
    note: str = ""


def get_all_providers() -> list[ProviderInfo]:
    """Return all available LLM providers with their models."""
    import os

    providers = []
    for key, info in {**CORE_PROVIDERS, **OPENAI_COMPATIBLE_PROVIDERS}.items():
        env_key = info.get("env_key")
        configured = env_key is None or bool(os.environ.get(env_key))
        providers.append(ProviderInfo(
            key=key,
            name=info["name"],
            models=info["models"],
            env_key=env_key,
            provider_type=info["type"],
            configured=configured,
            note=info.get("note", ""),
        ))
    return providers


def get_configured_providers() -> list[ProviderInfo]:
    """Return only providers that have their API keys configured."""
    return [p for p in get_all_providers() if p.configured]


def get_provider_summary() -> list[dict]:
    """Return a JSON-serializable summary for the frontend."""
    return [
        {
            "key": p.key,
            "name": p.name,
            "models": p.models,
            "configured": p.configured,
            "type": p.provider_type,
            "note": p.note,
        }
        for p in get_all_providers()
    ]