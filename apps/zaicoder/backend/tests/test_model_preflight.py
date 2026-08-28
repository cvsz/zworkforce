import json

import pytest

from zaicoder.model_preflight import ModelCapabilityResolver, ModelUnavailableError


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def test_resolves_and_caches_live_metadata():
    calls = []

    def opener(request, timeout):
        calls.append((request.full_url, timeout))
        return Response({"id": "model-a", "display_name": "Model A"})

    resolver = ModelCapabilityResolver("test-key", opener=opener)
    assert resolver.resolve("model-a")["display_name"] == "Model A"
    assert resolver.resolve("model-a")["id"] == "model-a"
    assert len(calls) == 1


def test_known_model_is_offline_fallback():
    def unavailable(*args, **kwargs):
        raise OSError("offline")

    resolver = ModelCapabilityResolver(
        "test-key",
        known_models={"model-a": {"id": "model-a"}},
        opener=unavailable,
    )
    assert resolver.resolve("model-a") == {"id": "model-a"}


def test_unknown_model_is_not_claimed_available_offline():
    def unavailable(*args, **kwargs):
        raise OSError("offline")

    resolver = ModelCapabilityResolver("test-key", opener=unavailable)
    with pytest.raises(ModelUnavailableError):
        resolver.resolve("unknown")
