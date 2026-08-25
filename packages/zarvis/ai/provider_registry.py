from __future__ import annotations

import importlib
import logging
from functools import lru_cache
from typing import Any, Callable, Dict, Iterable, NamedTuple


class ProviderSpec(NamedTuple):
    key: str
    module_path: str
    class_name: str


PROVIDER_SPECS: tuple[ProviderSpec, ...] = (
    ProviderSpec("openai", "ai.providers.openai", "OpenAIProvider"),
    ProviderSpec("gemini", "ai.providers.gemini", "GeminiProvider"),
    ProviderSpec("claude", "ai.providers.claude", "ClaudeProvider"),
    ProviderSpec("deepseek", "ai.providers.deepseek", "DeepSeekProvider"),
    ProviderSpec("ollama", "ai.providers.ollama", "OllamaProvider"),
    ProviderSpec("mistral", "ai.providers.mistral", "MistralProvider"),
    ProviderSpec("groq", "ai.providers.groq", "GroqProvider"),
    ProviderSpec("together", "ai.providers.together", "TogetherProvider"),
    ProviderSpec("openrouter", "ai.providers.openrouter", "OpenRouterProvider"),
    ProviderSpec("aws_bedrock", "ai.providers.aws_bedrock", "AWSBedrockProvider"),
    ProviderSpec("azure_openai", "ai.providers.azure_openai", "AzureOpenAIProvider"),
    ProviderSpec("cloudflare_ai", "ai.providers.cloudflare_ai", "CloudflareAIProvider"),
    ProviderSpec("perplexity", "ai.providers.perplexity", "PerplexityProvider"),
    ProviderSpec("huggingface", "ai.providers.huggingface", "HuggingFaceProvider"),
    ProviderSpec("replicate", "ai.providers.replicate", "ReplicateProvider"),
    ProviderSpec("fireworks", "ai.providers.fireworks", "FireworksProvider"),
    ProviderSpec("novita", "ai.providers.novita", "NovitaProvider"),
    ProviderSpec("deepinfra", "ai.providers.deepinfra", "DeepInfraProvider"),
    ProviderSpec("xai", "ai.providers.xai", "XAIProvider"),
    ProviderSpec("vertex_ai", "ai.providers.vertex_ai", "VertexAiProvider"),
    ProviderSpec("github_copilot", "ai.providers.github_copilot", "GithubCopilotProvider"),
    ProviderSpec("alibaba_dashscope", "ai.providers.alibaba_dashscope", "AlibabaDashscopeProvider"),
    ProviderSpec("tencent_hunyuan", "ai.providers.tencent_hunyuan", "TencentHunyuanProvider"),
    ProviderSpec("huawei_pangu", "ai.providers.huawei_pangu", "HuaweiPanguProvider"),
    ProviderSpec("zero1_ai", "ai.providers.zero1_ai", "Zero1AiProvider"),
    ProviderSpec("runpod", "ai.providers.runpod", "RunpodProvider"),
    ProviderSpec("vast_ai", "ai.providers.vast_ai", "VastAiProvider"),
    ProviderSpec("cerebras", "ai.providers.cerebras", "CerebrasProvider"),
    ProviderSpec("samba_nova", "ai.providers.samba_nova", "SambaNovaProvider"),
    ProviderSpec("onnx_web", "ai.providers.onnx_web", "OnnxWebProvider"),
    ProviderSpec("onnx_runtime", "ai.providers.onnx_runtime", "OnnxRuntimeProvider"),
    ProviderSpec("apple_coreml", "ai.providers.apple_coreml", "AppleCoremlProvider"),
    ProviderSpec("android_nnapi", "ai.providers.android_nnapi", "AndroidNnapiProvider"),
    ProviderSpec("lm_studio", "ai.providers.lm_studio", "LmStudioProvider"),
    ProviderSpec("vllm", "ai.providers.vllm", "VllmProvider"),
    ProviderSpec("llama_cpp", "ai.providers.llama_cpp", "LlamaCppProvider"),
    ProviderSpec("heygen", "ai.providers.heygen", "HeygenProvider"),
    ProviderSpec("synthesia", "ai.providers.synthesia", "SynthesiaProvider"),
    ProviderSpec("suno_ai", "ai.providers.suno_ai", "SunoAiProvider"),
    ProviderSpec("sora", "ai.providers.sora", "SoraProvider"),
    ProviderSpec("flux_ai", "ai.providers.flux_ai", "FluxAiProvider"),
    ProviderSpec("recraft_ai", "ai.providers.recraft_ai", "RecraftAiProvider"),
    ProviderSpec("replicate_deployments", "ai.providers.replicate_deployments", "ReplicateDeploymentsProvider"),
    ProviderSpec("chromadb_cloud", "ai.providers.chromadb_cloud", "ChromadbCloudProvider"),
    ProviderSpec("qdrant_cloud", "ai.providers.qdrant_cloud", "QdrantCloudProvider"),
    ProviderSpec("brave_search_api", "ai.providers.brave_search_api", "BraveSearchApiProvider"),
    ProviderSpec("google_search_api", "ai.providers.google_search_api", "GoogleSearchApiProvider"),
    ProviderSpec("exa_search", "ai.providers.exa_search", "ExaSearchProvider"),
    ProviderSpec("voyage_ai", "ai.providers.voyage_ai", "VoyageAiProvider"),
    ProviderSpec("runway", "ai.providers.runway", "RunwayProvider"),
)


@lru_cache(maxsize=None)
def _resolve_provider_class(module_path: str, class_name: str) -> type[Any]:
    module = importlib.import_module(module_path)
    provider_cls = getattr(module, class_name)
    if not callable(provider_cls):
        raise TypeError(f"{module_path}.{class_name} is not callable")
    return provider_cls


def build_provider_factories(
    specs: Iterable[ProviderSpec] = PROVIDER_SPECS,
    logger: logging.Logger | None = None,
) -> Dict[str, Callable[[], Any]]:
    factories: Dict[str, Callable[[], Any]] = {}
    for spec in specs:
        try:
            provider_cls = _resolve_provider_class(spec.module_path, spec.class_name)
        except (ModuleNotFoundError, AttributeError, TypeError) as exc:
            if logger:
                logger.debug("Skipping provider '%s': %s", spec.key, exc)
            continue
        if getattr(provider_cls, "supported", True) is not True:
            if logger:
                logger.debug("Skipping provider '%s': production adapter is unavailable", spec.key)
            continue

        def factory(provider_cls: type[Any] = provider_cls) -> Any:
            return provider_cls()

        factories[spec.key] = factory
    return factories
