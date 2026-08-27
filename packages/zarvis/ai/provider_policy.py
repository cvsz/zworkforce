from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


class RoutingMode(str, Enum):
    ZERO = "zero"
    ECO = "eco"
    BALANCED = "balanced"
    MAX = "max"


class ProviderTier(str, Enum):
    LOCAL = "local"
    FREE_TIER = "free_tier"
    STANDARD = "standard"
    PREMIUM = "premium"


@dataclass(frozen=True)
class ProviderPolicy:
    tier: ProviderTier
    external: bool


# This catalog is intentionally conservative. A provider is only marked LOCAL
# when zWorkforce can address a self-hosted/local runtime without sending the
# prompt to an external service. Remote services are not treated as "free"
# merely because they may offer promotional or account-specific free quotas.
PROVIDER_POLICIES: Mapping[str, ProviderPolicy] = {
    "ollama": ProviderPolicy(ProviderTier.LOCAL, external=False),
    "vllm": ProviderPolicy(ProviderTier.LOCAL, external=False),
    "lm_studio": ProviderPolicy(ProviderTier.LOCAL, external=False),
    "llama_cpp": ProviderPolicy(ProviderTier.LOCAL, external=False),
    "onnx_runtime": ProviderPolicy(ProviderTier.LOCAL, external=False),
    "apple_coreml": ProviderPolicy(ProviderTier.LOCAL, external=False),
    "android_nnapi": ProviderPolicy(ProviderTier.LOCAL, external=False),
    "openai": ProviderPolicy(ProviderTier.STANDARD, external=True),
    "gemini": ProviderPolicy(ProviderTier.STANDARD, external=True),
    "claude": ProviderPolicy(ProviderTier.PREMIUM, external=True),
    "deepseek": ProviderPolicy(ProviderTier.STANDARD, external=True),
    "mistral": ProviderPolicy(ProviderTier.STANDARD, external=True),
    "groq": ProviderPolicy(ProviderTier.STANDARD, external=True),
    "together": ProviderPolicy(ProviderTier.STANDARD, external=True),
    "openrouter": ProviderPolicy(ProviderTier.STANDARD, external=True),
    "huggingface": ProviderPolicy(ProviderTier.STANDARD, external=True),
    "cloudflare_ai": ProviderPolicy(ProviderTier.STANDARD, external=True),
}


def normalize_routing_mode(value: object) -> RoutingMode:
    if value is None:
        return RoutingMode.BALANCED
    try:
        return RoutingMode(str(value).strip().lower())
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in RoutingMode)
        raise ValueError(f"Unsupported routing mode {value!r}; expected one of: {allowed}") from exc


def provider_policy(provider: str) -> ProviderPolicy:
    # Unknown providers fail conservative: treat them as external/paid-capable.
    return PROVIDER_POLICIES.get(
        provider,
        ProviderPolicy(ProviderTier.STANDARD, external=True),
    )


def is_allowed_in_mode(provider: str, mode: RoutingMode) -> bool:
    policy = provider_policy(provider)
    if mode is RoutingMode.ZERO:
        return policy.tier is ProviderTier.LOCAL and not policy.external
    return True


def filter_provider_chain(
    providers: Iterable[str],
    mode: RoutingMode,
    available: Iterable[str],
) -> list[str]:
    available_set = set(available)
    result: list[str] = []
    for provider in providers:
        if provider in result or provider not in available_set:
            continue
        if is_allowed_in_mode(provider, mode):
            result.append(provider)
    return result
