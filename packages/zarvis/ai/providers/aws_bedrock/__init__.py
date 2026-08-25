from __future__ import annotations

import json
import os
from typing import Any


class AWSBedrockProvider:
    """AWS Bedrock Runtime adapter using the AWS credential provider chain.

    Credentials are intentionally not read into application state or included
    in errors. In production, boto3 resolves them from the standard AWS chain
    (workload identity, task role, instance profile, or environment).
    """

    supported = True

    def __init__(
        self,
        *,
        client: Any | None = None,
        region: str | None = None,
        default_model: str | None = None,
    ) -> None:
        self.region = str(region or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1")
        self.default_model = str(
            default_model
            or os.getenv("BEDROCK_MODEL")
            or "anthropic.claude-3-5-sonnet-20241022-v2:0"
        )
        self._client = client

    def _runtime_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise RuntimeError("AWS Bedrock requires the zworkforce[aws] extra") from exc
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=self.region,
            config=Config(
                connect_timeout=5,
                read_timeout=60,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )
        return self._client

    @staticmethod
    def _bounded_options(kwargs: dict[str, Any]) -> tuple[int, float]:
        try:
            max_tokens = max(1, min(int(kwargs.get("max_tokens", 4096)), 8192))
            temperature = max(0.0, min(float(kwargs.get("temperature", 0.3)), 2.0))
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid Bedrock generation options") from exc
        return max_tokens, temperature

    def _payload(self, model: str, prompt: str, system_prompt: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        max_tokens, temperature = self._bounded_options(kwargs)
        model_key = model.lower()
        if model_key.startswith("anthropic.") or model_key.startswith("claude"):
            payload: dict[str, Any] = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system_prompt:
                payload["system"] = system_prompt
            return payload
        if model_key.startswith("amazon.titan"):
            text = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            return {
                "inputText": text,
                "textGenerationConfig": {
                    "maxTokenCount": max_tokens,
                    "temperature": temperature,
                },
            }
        raise ValueError(
            "unsupported Bedrock model family; configure an anthropic.* or amazon.titan.* model"
        )

    @staticmethod
    def _decode_body(response: dict[str, Any]) -> dict[str, Any]:
        body = response.get("body")
        if hasattr(body, "read"):
            body = body.read()
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        if not isinstance(body, str):
            raise RuntimeError("Bedrock returned an invalid response body")
        try:
            decoded = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Bedrock returned malformed JSON") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError("Bedrock returned an invalid response object")
        return decoded

    @staticmethod
    def _response_text(model: str, response: dict[str, Any]) -> str:
        decoded = AWSBedrockProvider._decode_body(response)
        if model.lower().startswith("anthropic.") or model.lower().startswith("claude"):
            content = decoded.get("content")
            if isinstance(content, list):
                text = "".join(
                    str(item.get("text", ""))
                    for item in content
                    if isinstance(item, dict) and item.get("type") == "text"
                ).strip()
                if text:
                    return text
        elif model.lower().startswith("amazon.titan"):
            results = decoded.get("results")
            if isinstance(results, list) and results and isinstance(results[0], dict):
                text = str(results[0].get("outputText", "")).strip()
                if text:
                    return text
        raise RuntimeError("Bedrock returned no text content")

    def generate(self, prompt: str, system_prompt: str = "", **kwargs: Any) -> str:
        prompt = str(prompt or "")
        if not prompt.strip():
            raise ValueError("Bedrock prompt is required")
        model = str(kwargs.get("model") or self.default_model)
        payload = self._payload(model, prompt, str(system_prompt or ""), kwargs)
        try:
            response = self._runtime_client().invoke_model(
                modelId=model,
                body=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
                contentType="application/json",
                accept="application/json",
            )
        except Exception as exc:
            # Do not surface provider responses or credential-bearing details.
            raise RuntimeError("Bedrock invocation failed") from exc
        return self._response_text(model, response)
