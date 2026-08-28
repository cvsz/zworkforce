from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, Mapping

from ai.caching import AICache
from ai.cost_control import AICostController
from ai.fallback import AIFallbackManager
from ai.guardrails import AIGuardrails
from ai.metrics import AIMetricsTracker
from ai.prompt_registry import PromptRegistry
from ai.provider_policy import RoutingMode, filter_provider_chain, normalize_routing_mode
from ai.provider_registry import PROVIDER_SPECS, build_provider_factories
from ai.routing_rules import AIRoutingRules

ProviderFactory = Callable[[], Any]
ProviderFactoryMap = Mapping[str, ProviderFactory]


class AIRouter:
    def __init__(
        self,
        provider_factories: ProviderFactoryMap | None = None,
        cache: AICache | None = None,
        cost_controller: AICostController | None = None,
        fallback_manager: AIFallbackManager | None = None,
        prompt_registry: PromptRegistry | None = None,
        guardrails: AIGuardrails | None = None,
        routing_rules: AIRoutingRules | None = None,
        metrics: AIMetricsTracker | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.provider_specs = PROVIDER_SPECS
        if provider_factories is None:
            self.provider_factories = build_provider_factories(logger=self.logger)
        else:
            self.provider_factories = dict(provider_factories)
        self.providers = self.provider_factories
        self.cache = cache or AICache()
        self.cost_controller = cost_controller or AICostController()
        self.fallback_manager = fallback_manager or AIFallbackManager()
        self.prompt_registry = prompt_registry or PromptRegistry()
        self.guardrails = guardrails or AIGuardrails()
        self.routing_rules = routing_rules or AIRoutingRules()
        self.metrics = metrics or AIMetricsTracker()

    def route_request(
        self,
        prompt_id: str,
        context: Dict[str, Any],
        preferred_provider: str = "claude",
    ) -> Dict[str, Any]:
        routing_mode = normalize_routing_mode(context.get("routing_mode"))

        # Exhausting the configured spend budget must never silently continue to
        # another external provider. Downgrade to the fail-closed local-only
        # policy instead; callers can explicitly raise the budget out of band.
        if self.cost_controller.check_budget_exceeded():
            routing_mode = RoutingMode.ZERO

        prompt_content = self.prompt_registry.render(prompt_id, context)
        system_prompt = self.prompt_registry.get_system_prompt(prompt_id) or context.get("system_prompt", "")

        is_safe, safety_reason = self.guardrails.validate_input(prompt_content)
        if not is_safe:
            return {
                "status": "blocked",
                "reason": safety_reason,
                "data": "Request blocked by safety policy.",
            }

        chosen_provider = self.routing_rules.determine_optimal_provider(prompt_content, preferred_provider)

        cached_res = self.cache.get(prompt_id, context)
        if cached_res:
            self.metrics.record_cache(hit=True)
            self.logger.info("Cache hit for prompt: %s", prompt_id)
            return cached_res

        self.metrics.record_cache(hit=False)
        candidate_chain = [
            chosen_provider,
            "gemini",
            "deepseek",
            "ollama",
            "vllm",
            "lm_studio",
            "llama_cpp",
            "onnx_runtime",
        ]
        provider_chain = filter_provider_chain(
            candidate_chain,
            routing_mode,
            self.provider_factories.keys(),
        )
        if not provider_chain:
            raise RuntimeError(
                f"No provider is available under routing mode '{routing_mode.value}'. "
                "ZERO mode requires a configured local runtime."
            )

        def execute_fn(provider_name: str) -> Dict[str, Any]:
            start = time.monotonic()
            try:
                response = self._execute_with_provider(provider_name, prompt_content, system_prompt, context)
                self.metrics.record_call(provider_name, time.monotonic() - start, success=True)
                return response
            except Exception:
                self.metrics.record_call(provider_name, time.monotonic() - start, success=False)
                raise

        try:
            response = self.fallback_manager.execute_with_fallback(provider_chain, execute_fn)
            response["data"] = self.guardrails.clean_output(response["data"])
            self.cost_controller.track_call(response["provider"])
            self.cache.set(prompt_id, context, response)
            return response
        except Exception as exc:
            self.logger.critical("Global routing failure: %s", exc)
            raise

    def _execute_with_provider(
        self,
        provider_name: str,
        prompt: str,
        system_prompt: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        provider_factory = self.provider_factories.get(provider_name)
        if provider_factory is None:
            raise ValueError(f"Unknown provider: {provider_name}")

        provider = provider_factory()
        if not hasattr(provider, "generate"):
            raise TypeError(f"Provider '{provider_name}' does not implement generate()")

        options = context.get("options", {})
        result_text = provider.generate(prompt, system_prompt=system_prompt, **options)
        return {"status": "success", "data": result_text, "provider": provider_name}
