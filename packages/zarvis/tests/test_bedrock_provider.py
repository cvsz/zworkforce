from __future__ import annotations

import io
import json
import unittest

from ai.providers._unsupported import UnsupportedProviderError
from ai.providers.alibaba_dashscope import AlibabaDashscopeProvider
from ai.providers.aws_bedrock import AWSBedrockProvider


class FakeBedrockClient:
    def __init__(self, body: dict[str, object]) -> None:
        self.body = body
        self.calls: list[dict[str, object]] = []

    def invoke_model(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return {"body": io.BytesIO(json.dumps(self.body).encode("utf-8"))}


class BedrockProviderTests(unittest.TestCase):
    def test_anthropic_invocation_uses_real_runtime_contract(self) -> None:
        client = FakeBedrockClient({"content": [{"type": "text", "text": "real response"}]})
        provider = AWSBedrockProvider(client=client, region="eu-west-1")

        self.assertEqual(provider.generate("hello", "system", max_tokens=12, temperature=0.5), "real response")
        self.assertEqual(len(client.calls), 1)
        request = client.calls[0]
        self.assertEqual(request["modelId"], "anthropic.claude-3-5-sonnet-20241022-v2:0")
        payload = json.loads(request["body"])
        self.assertEqual(payload["anthropic_version"], "bedrock-2023-05-31")
        self.assertEqual(payload["system"], "system")
        self.assertEqual(payload["max_tokens"], 12)

    def test_titan_response_is_supported(self) -> None:
        client = FakeBedrockClient({"results": [{"outputText": "titan response"}]})
        provider = AWSBedrockProvider(client=client, default_model="amazon.titan-text-express-v1")
        self.assertEqual(provider.generate("hello"), "titan response")

    def test_unimplemented_provider_cannot_fabricate_success(self) -> None:
        with self.assertRaises(UnsupportedProviderError):
            AlibabaDashscopeProvider().generate("hello")


if __name__ == "__main__":
    unittest.main()
