from pathlib import Path

import pytest

from zeaz_provider.config import load_settings
from zeaz_provider.security import client_key_digest

OPENROUTER_FREE_MODEL_IDS = (
    "inclusionai/ling-3.0-flash:free",
    "poolside/laguna-s-2.1:free",
    "poolside/laguna-xs-2.1:free",
    "cohere/north-mini-code:free",
    "nvidia/nemotron-3.5-content-safety:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "google/lyria-3-pro-preview",
    "google/lyria-3-clip-preview",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openrouter/free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "nvidia/nemotron-nano-9b-v2:free",
    "openai/gpt-oss-20b:free",
)


def test_load_config_expands_environment(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TEST_PROVIDER_KEY", "secret")
    path = tmp_path / "providers.yaml"
    path.write_text(
        """
default_model: test
providers:
  local:
    api: openai
    base_url: http://localhost:1/v1
    api_key: ${TEST_PROVIDER_KEY}
models:
  test:
    provider: local
    model: test-model
""",
        encoding="utf-8",
    )
    value = load_settings(path)
    assert value.providers["local"].api_key == "secret"
    assert value.models["test"].primary.model == "test-model"


def test_disabled_provider_is_omitted(monkeypatch):
    monkeypatch.setenv("CUSTOM_PROVIDER_ENABLED", "false")
    value = load_settings("config/providers.example.yaml")
    assert "custom" not in value.providers


def test_qwen_free_route_uses_local_qwen_by_default(monkeypatch):
    monkeypatch.delenv("FREE_CLOUD_FALLBACK_ENABLED", raising=False)
    value = load_settings("config/providers.example.yaml")
    route = value.models["zeaz-qwen-free"]
    assert route.primary.provider == "ollama"
    assert route.primary.model == "qwen3:8b"
    assert route.fallbacks == ()


def test_qwen_free_route_can_use_openrouter_free_fallback(monkeypatch):
    monkeypatch.setenv("FREE_CLOUD_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("OPENROUTER_QWEN_FREE_MODEL", "qwen/example:free")
    value = load_settings("config/providers.example.yaml")
    route = value.models["zeaz-qwen-free"]
    assert route.fallbacks[0].provider == "openrouter-free"
    assert route.fallbacks[0].model == "qwen/example:free"


def test_kimi_free_route_uses_local_kimi_by_default(monkeypatch):
    monkeypatch.delenv("FREE_CLOUD_FALLBACK_ENABLED", raising=False)
    value = load_settings("config/providers.example.yaml")
    route = value.models["zeaz-kimi-free"]
    assert route.primary.provider == "ollama"
    assert route.primary.model == "kimi-k2:latest"
    assert route.fallbacks == ()


def test_kimi_free_route_can_use_openrouter_free_fallback(monkeypatch):
    monkeypatch.setenv("FREE_CLOUD_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("OPENROUTER_KIMI_FREE_MODEL", "moonshotai/example:free")
    value = load_settings("config/providers.example.yaml")
    route = value.models["zeaz-kimi-free"]
    assert route.fallbacks[0].provider == "openrouter-free"
    assert route.fallbacks[0].model == "moonshotai/example:free"


def test_openrouter_free_routes_are_omitted_until_cloud_fallback_is_enabled(monkeypatch):
    monkeypatch.delenv("FREE_CLOUD_FALLBACK_ENABLED", raising=False)
    value = load_settings("config/providers.example.yaml")
    assert "zeaz-openrouter-free-all" not in value.models
    assert "zeaz-free-openai-gpt-oss-20b" not in value.models


def test_openrouter_free_all_route_connects_current_live_free_models(monkeypatch):
    monkeypatch.setenv("FREE_CLOUD_FALLBACK_ENABLED", "true")
    value = load_settings("config/providers.example.yaml")
    route = value.models["zeaz-openrouter-free-all"]
    configured = (route.primary.model, *(target.model for target in route.fallbacks))
    assert route.primary.model == "openrouter/free"
    assert set(configured) == set(OPENROUTER_FREE_MODEL_IDS)
    assert len(configured) == len(OPENROUTER_FREE_MODEL_IDS)


def test_openrouter_free_direct_model_routes_are_connected(monkeypatch):
    monkeypatch.setenv("FREE_CLOUD_FALLBACK_ENABLED", "true")
    value = load_settings("config/providers.example.yaml")
    aliases = {
        route.primary.model: alias
        for alias, route in value.models.items()
        if alias.startswith("zeaz-free-")
        and route.primary.provider == "openrouter-free"
    }
    assert set(OPENROUTER_FREE_MODEL_IDS).issubset(aliases)


def test_redis_rate_limit_backend_requires_url(monkeypatch):
    monkeypatch.setenv("ZEAZ_RATE_LIMIT_BACKEND", "redis")
    monkeypatch.delenv("ZEAZ_REDIS_URL", raising=False)
    with pytest.raises(RuntimeError, match="ZEAZ_REDIS_URL is required"):
        load_settings("config/providers.example.yaml")


def test_redis_rate_limit_backend_configuration(monkeypatch):
    monkeypatch.setenv("ZEAZ_RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("ZEAZ_REDIS_URL", "redis://localhost:6379/1")
    value = load_settings("config/providers.example.yaml")
    assert value.rate_limit_backend == "redis"
    assert value.redis_url == "redis://localhost:6379/1"


def test_trusted_proxy_cidrs_are_normalized(monkeypatch):
    monkeypatch.setenv("ZEAZ_TRUSTED_PROXY_CIDRS", "192.0.2.9/24,2001:db8::1/32")
    value = load_settings("config/providers.example.yaml")
    assert value.trusted_proxy_cidrs == ("192.0.2.0/24", "2001:db8::/32")


def test_invalid_trusted_proxy_cidr_is_rejected(monkeypatch):
    monkeypatch.setenv("ZEAZ_TRUSTED_PROXY_CIDRS", "cloudflare.example")
    with pytest.raises(RuntimeError, match="invalid CIDR"):
        load_settings("config/providers.example.yaml")


def test_plaintext_client_keys_are_hashed_immediately(monkeypatch):
    monkeypatch.setenv("ZEAZ_CLIENT_KEYS", "legacy-client-key")
    monkeypatch.delenv("ZEAZ_CLIENT_KEY_HASHES", raising=False)
    value = load_settings("config/providers.example.yaml")
    assert value.client_key_hashes == frozenset({client_key_digest("legacy-client-key")})
    assert "legacy-client-key" not in repr(value)


def test_hashed_client_key_configuration(monkeypatch):
    digest = client_key_digest("production-client-key")
    monkeypatch.delenv("ZEAZ_CLIENT_KEYS", raising=False)
    monkeypatch.setenv("ZEAZ_CLIENT_KEY_HASHES", f"sha256:{digest.hex()}")
    value = load_settings("config/providers.example.yaml")
    assert value.client_key_hashes == frozenset({digest})


def test_invalid_client_key_hash_is_rejected(monkeypatch):
    monkeypatch.setenv("ZEAZ_CLIENT_KEY_HASHES", "sha256:not-a-hash")
    with pytest.raises(RuntimeError, match="invalid SHA-256 hash"):
        load_settings("config/providers.example.yaml")


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("ZEAZ_MAX_CONCURRENT_REQUESTS", "0", "must be at least 1"),
        ("ZEAZ_MAX_RESPONSE_BYTES", "100", "must be at least 1024"),
    ],
)
def test_invalid_request_limits_are_rejected(monkeypatch, name, value, message):
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError, match=message):
        load_settings("config/providers.example.yaml")


def test_malformed_top_level_sections_are_rejected(tmp_path: Path):
    path = tmp_path / "providers.yaml"
    path.write_text("providers: []\nmodels: {}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="providers must be an object"):
        load_settings(path)


def test_unhashable_fallback_provider_is_rejected(tmp_path: Path):
    path = tmp_path / "providers.yaml"
    path.write_text(
        """
providers:
  local:
    api: openai
    base_url: http://localhost:1/v1
models:
  test:
    provider: local
    model: test-model
    fallbacks:
      - provider: [invalid]
        model: other-model
""",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="Invalid model route fallback"):
        load_settings(path)
