from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest

from zworkforce.config import _providers_from_env


@pytest.mark.parametrize(
    ("providers", "message"),
    [
        (["not-an-object"], "each provider must be an object"),
        (
            [{"name": "provider-a", "models": "not-an-object"}],
            "provider provider-a models must be an object",
        ),
    ],
)
def test_provider_config_rejects_wrong_json_types_with_type_error(providers, message):
    with (
        patch.dict(
            os.environ,
            {"ZWORKFORCE_PROVIDERS_JSON": json.dumps(providers)},
            clear=True,
        ),
        pytest.raises(TypeError, match=message),
    ):
        _providers_from_env("development")
