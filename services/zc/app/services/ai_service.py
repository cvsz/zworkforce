"""Application service adapting the legacy AI engine to enterprise API use cases."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone
from functools import partial
from uuid import uuid4

from app.models.ai import AICapabilities, AIModel, AIResponse, AIResponseRequest, AIUsage

from ..core.config import Config, get_config
from .ai_provider import (
    AnthropicCoderAdapter,
    EmbeddedLiteLLMAdapter,
    ProviderGeneration,
)
from .capabilities import PERSONALITIES, SKILLS


AGENT_SYSTEM_PROMPTS: dict[str, str] = {
    "code_generator": (
        "You are a full-project code generation agent. Produce complete, runnable code."
    ),
    "code_reviewer": (
        "You are a code review agent. Focus on correctness, readability, and maintainability."
    ),
    "testing_agent": (
        "You are a testing agent. Cover edge cases and failure modes."
    ),
    "documentation_agent": (
        "You are a documentation agent. Write clear documentation for new readers."
    ),
    "optimizer": (
        "You are a performance optimization agent. Propose measurable improvements."
    ),
    "security_auditor": (
        "You are a security audit agent. Identify vulnerabilities and rate their severity."
    ),
    "full_stack": (
        "You are a full-stack engineering agent. Consider frontend, backend, and data layers."
    ),
}


class AIServiceError(RuntimeError):
    """Operational failure safe to map to a stable API error code."""


class UnknownCapabilityError(ValueError):
    """A requested agent, personality, or skill does not exist."""


class AIService:
    """Own AI use-case orchestration independently of HTTP and argparse."""

    def __init__(
        self,
        coder_factory: Callable[..., object] | None = None,
        *,
        config: Config | None = None,
    ) -> None:
        self._coder_factory = coder_factory
        self._config = config or get_config()

    @staticmethod
    def capabilities() -> AICapabilities:
        """Return capabilities owned by the server boundary."""
        return AICapabilities(
            agents=sorted(AGENT_SYSTEM_PROMPTS),
            personalities=sorted(PERSONALITIES),
            skills=sorted(SKILLS),
        )

    @staticmethod
    def _system_prompt(request: AIResponseRequest) -> str | None:
        parts = [request.system] if request.system else []

        if request.personality:
            personality_prompt = PERSONALITIES.get(request.personality)
            if personality_prompt is None:
                raise UnknownCapabilityError(
                    f"Unknown personality: {request.personality}"
                )
            parts.append(personality_prompt)

        if request.agent:
            prompt = AGENT_SYSTEM_PROMPTS.get(request.agent)
            if prompt is None:
                raise UnknownCapabilityError(f"Unknown agent: {request.agent}")
            parts.append(prompt)

        if request.skill:
            skill_description = SKILLS.get(request.skill)
            if skill_description is None:
                raise UnknownCapabilityError(f"Unknown skill: {request.skill}")
            parts.append(
                f"Skill focus — {request.skill}: {skill_description}"
            )

        return "\n\n".join(parts) or None

    def _create_coder(self, request: AIResponseRequest) -> object:
        options: dict[str, object] = {
            "model": request.model,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "personality_style": request.personality,
            "service_tier": request.service_tier,
            "inference_geo": request.inference_geo,
            "fast_mode": request.fast_mode,
        }
        if self._coder_factory is not None:
            factory = self._coder_factory
        elif self._config.ai_provider == "litellm":
            factory = EmbeddedLiteLLMAdapter
            options.update(
                {
                    "config_path": self._config.litellm_config_path,
                    "model": request.model or self._config.litellm_model,
                    "timeout_seconds": self._config.litellm_timeout_seconds,
                }
            )
        else:
            factory = AnthropicCoderAdapter

        return factory(
            **options,
        )

    async def create_response(self, request: AIResponseRequest) -> AIResponse:
        """Execute blocking legacy inference outside the event loop."""
        system = self._system_prompt(request)
        coder = self._create_coder(request)
        generate = getattr(coder, "generate", None)
        if not callable(generate):
            raise AIServiceError("AI provider adapter is unavailable")

        call = partial(
            generate,
            request.prompt,
            system=system,
            file_content=request.file_content,
            history=[message.model_dump() for message in request.history],
        )
        output = call()
        if inspect.isawaitable(output):
            output = await output
        usage = AIUsage()
        if isinstance(output, ProviderGeneration):
            output_text = output.text
            model = output.model
            usage = AIUsage(
                input_tokens=output.input_tokens,
                output_tokens=output.output_tokens,
            )
        elif isinstance(output, str):
            output_text = output
            model = str(getattr(coder, "model", request.model or "unknown"))
        else:
            raise AIServiceError("AI provider returned an invalid response")
        if output_text.startswith("[ERROR]") or output_text.startswith("[API ERROR"):
            raise AIServiceError("AI provider request failed")

        return AIResponse(
            id=f"air_{uuid4().hex}",
            created_at=datetime.now(timezone.utc),
            model=model,
            output_text=output_text,
            usage=usage,
        )

    async def stream_response(
        self, request: AIResponseRequest
    ) -> AsyncIterator[dict[str, object]]:
        """Yield normalized lifecycle events for one provider response."""
        system = self._system_prompt(request)
        coder = self._create_coder(request)
        stream = getattr(coder, "stream", None)
        response_id = f"air_{uuid4().hex}"
        created_at = datetime.now(timezone.utc)
        yield {
            "type": "response.started",
            "response": {
                "id": response_id,
                "object": "ai.response",
                "created_at": created_at.isoformat(),
            },
        }

        if not callable(stream):
            response = await self.create_response(request)
            yield {
                "type": "response.output_text.delta",
                "delta": response.output_text,
            }
            yield {
                "type": "response.completed",
                "response": response.model_dump(mode="json"),
            }
            return

        output_parts: list[str] = []
        model = str(getattr(coder, "model", request.model or "unknown"))
        input_tokens: int | None = None
        output_tokens: int | None = None
        try:
            chunks = stream(
                request.prompt,
                system=system,
                file_content=request.file_content,
                history=[message.model_dump() for message in request.history],
            )
            async for chunk in chunks:
                if chunk.model:
                    model = chunk.model
                if chunk.input_tokens is not None:
                    input_tokens = chunk.input_tokens
                if chunk.output_tokens is not None:
                    output_tokens = chunk.output_tokens
                if chunk.text:
                    output_parts.append(chunk.text)
                    yield {
                        "type": "response.output_text.delta",
                        "delta": chunk.text,
                    }
        except Exception as exc:
            raise AIServiceError("AI provider stream failed") from exc

        output_text = "".join(output_parts)
        if not output_text:
            raise AIServiceError("AI provider returned no text")
        response = AIResponse(
            id=response_id,
            created_at=created_at,
            model=model,
            output_text=output_text,
            usage=AIUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
        )
        yield {
            "type": "response.completed",
            "response": response.model_dump(mode="json"),
        }

    async def list_models(self) -> list[AIModel]:
        """List model aliases visible through the configured provider."""
        if self._config.ai_provider != "litellm":
            return []
        adapter = EmbeddedLiteLLMAdapter(
            config_path=self._config.litellm_config_path,
            model=self._config.litellm_model,
            timeout_seconds=self._config.litellm_timeout_seconds,
        )
        return [AIModel(id=model_id) for model_id in await adapter.list_models()]

    async def provider_ready(self) -> bool:
        """Return whether the configured inference provider is reachable."""
        if self._config.ai_provider != "litellm":
            return True
        adapter = EmbeddedLiteLLMAdapter(
            config_path=self._config.litellm_config_path,
            model=self._config.litellm_model,
            timeout_seconds=self._config.litellm_timeout_seconds,
        )
        return await adapter.is_live()


_service: AIService | None = None


def get_ai_service_instance() -> AIService:
    """Return the process-local stateless AI application service."""
    global _service
    if _service is None:
        _service = AIService()
    return _service


async def get_ai_service() -> AIService:
    """FastAPI dependency that avoids the synchronous dependency threadpool."""
    return get_ai_service_instance()


__all__ = [
    "AGENT_SYSTEM_PROMPTS",
    "AIService",
    "AIServiceError",
    "UnknownCapabilityError",
    "get_ai_service",
    "get_ai_service_instance",
]
