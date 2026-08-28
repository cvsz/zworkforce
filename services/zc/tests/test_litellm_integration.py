"""Contract tests for the embedded LiteLLM Router integration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from app.core.config import Config
from app.models.ai import AIResponseRequest
from app.services.ai_provider import EmbeddedLiteLLMAdapter, ProviderGeneration
from app.services.ai_service import AIService


class FakeRouter:
    """Deterministic LiteLLM Router double that performs no network calls."""

    request: dict[str, Any] = {}

    async def acompletion(self, **kwargs: Any) -> Any:
        type(self).request = kwargs
        if kwargs.get("stream"):
            async def chunks():
                yield SimpleNamespace(
                    choices=[
                        SimpleNamespace(delta=SimpleNamespace(content="routed "))
                    ],
                    model="resolved-deployment",
                    usage=None,
                )
                yield SimpleNamespace(
                    choices=[
                        SimpleNamespace(delta=SimpleNamespace(content="inside zc"))
                    ],
                    model="resolved-deployment",
                    usage=SimpleNamespace(
                        prompt_tokens=11,
                        completion_tokens=7,
                    ),
                )

            return chunks()
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="routed inside zc")
                )
            ],
            model="resolved-deployment",
            usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7),
        )

    def get_model_names(self) -> list[str]:
        return ["zc-default", "fast", "zc-default"]


@pytest.mark.asyncio
async def test_embedded_adapter_calls_router_without_http(tmp_path: Path) -> None:
    adapter = EmbeddedLiteLLMAdapter(
        config_path=tmp_path / "litellm-config.yaml",
        model="zc-default",
        temperature=0.2,
        router=FakeRouter(),
    )

    output = await adapter.generate(
        "fix the test",
        system="You are a coding agent.",
        history=[{"role": "assistant", "content": "ready"}],
    )

    assert output == ProviderGeneration(
        text="routed inside zc",
        model="resolved-deployment",
        input_tokens=11,
        output_tokens=7,
    )
    assert FakeRouter.request["model"] == "zc-default"
    assert FakeRouter.request["messages"] == [
        {"role": "system", "content": "You are a coding agent."},
        {"role": "assistant", "content": "ready"},
        {"role": "user", "content": "fix the test"},
    ]
    assert FakeRouter.request["timeout"] == 120


@pytest.mark.asyncio
async def test_embedded_adapter_streams_without_proxy_process(
    tmp_path: Path,
) -> None:
    adapter = EmbeddedLiteLLMAdapter(
        config_path=tmp_path / "litellm-config.yaml",
        model="zc-default",
        router=FakeRouter(),
    )

    chunks = [chunk async for chunk in adapter.stream("stream this")]

    assert "".join(chunk.text for chunk in chunks) == "routed inside zc"
    assert chunks[-1].model == "resolved-deployment"
    assert chunks[-1].input_tokens == 11
    assert chunks[-1].output_tokens == 7
    assert FakeRouter.request["stream"] is True


@pytest.mark.asyncio
async def test_embedded_adapter_lists_local_router_aliases(tmp_path: Path) -> None:
    adapter = EmbeddedLiteLLMAdapter(
        config_path=tmp_path / "litellm-config.yaml",
        router=FakeRouter(),
    )

    assert await adapter.list_models() == ["fast", "zc-default"]
    assert await adapter.is_live() is True


def test_ai_service_selects_embedded_litellm(tmp_path: Path) -> None:
    config_path = tmp_path / "litellm-config.yaml"
    config_path.write_text("model_list: []\n")
    config = Config(
        environment="test",
        ai_provider="litellm",
        litellm_config_path=config_path,
        litellm_model="zc-default",
    )
    service = AIService(config=config)

    adapter = service._create_coder(AIResponseRequest(prompt="hello"))

    assert isinstance(adapter, EmbeddedLiteLLMAdapter)
    assert adapter.config_path == config_path.resolve()
    assert adapter.model == "zc-default"


@pytest.mark.asyncio
async def test_ai_service_preserves_router_model_and_usage() -> None:
    class ResultCoder:
        model = "requested-model"

        def __init__(self, **_options: object) -> None:
            pass

        async def generate(self, *_args: object, **_kwargs: object) -> ProviderGeneration:
            return ProviderGeneration(
                text="complete",
                model="resolved-model",
                input_tokens=5,
                output_tokens=3,
            )

    service = AIService(ResultCoder, config=Config(environment="test"))

    response = await service.create_response(AIResponseRequest(prompt="hello"))

    assert response.output_text == "complete"
    assert response.model == "resolved-model"
    assert response.usage.input_tokens == 5
    assert response.usage.output_tokens == 3


def test_embedded_litellm_requires_existing_config(tmp_path: Path) -> None:
    config = Config(
        environment="test",
        ai_provider="litellm",
        litellm_config_path=tmp_path / "missing.yaml",
    )

    with pytest.raises(RuntimeError, match="LiteLLM config not found"):
        config.validate()


def test_config_reads_embedded_router_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "router.yaml"
    config_path.write_text("model_list: []\n")
    monkeypatch.setenv("AI_PROVIDER", "litellm")
    monkeypatch.setenv("LITELLM_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("LITELLM_MODEL", "fast")

    config = Config.from_env()

    assert config.litellm_config_path == config_path
    assert config.litellm_model == "fast"


def test_compose_starts_only_zc_with_embedded_router() -> None:
    compose = yaml.safe_load(Path("docker-compose.yml").read_text())

    assert set(compose["services"]) == {"zc"}
    service = compose["services"]["zc"]
    assert "depends_on" not in service
    assert service["environment"]["AI_PROVIDER"] == "${AI_PROVIDER:-litellm}"
    assert (
        service["environment"]["LITELLM_CONFIG_PATH"]
        == "/app/litellm-config.yaml"
    )
    assert service["environment"]["FRONTEND_ENABLED"] == "true"
    assert service["environment"]["REDIS_ENABLED"] == "false"
    assert service["network_mode"] == "host"
    assert "ports" not in service


def test_router_config_has_no_proxy_master_key() -> None:
    router_config = yaml.safe_load(Path("litellm-config.yaml").read_text())

    assert "general_settings" not in router_config
    assert router_config["router_settings"]["num_retries"] == 2
    assert any(
        model["model_name"] == "zc-default"
        for model in router_config["model_list"]
    )


def test_runtime_dependencies_pin_embedded_litellm() -> None:
    requirements = Path("requirements-deploy.in").read_text().splitlines()

    assert "litellm==1.94.0rc1" in requirements
