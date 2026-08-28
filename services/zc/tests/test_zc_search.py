"""tests/test_zc_search.py

Covers zc_search.py's v1.24.0 fix: this module's own separate
WEB_SEARCH_TOOL/WEB_FETCH_TOOL constants had drifted from
zc_tools.py's version tracking entirely (still on
web_search_20250305/web_fetch_20250124). Bumped to
web_search_20260318/web_fetch_20260318 and threaded response_inclusion
through — see docs/36_upgrade_v1.24.0_audit_and_impl.md Finding 1.
"""
import types
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def search_mod(monkeypatch):
    """Import zc_search with a fake anthropic module installed, mirroring
    the mocking style used for zc_agents_sdk's tests in this repo."""
    fake_anthropic = types.ModuleType("anthropic")

    class _FakeAnthropicClient:
        def __init__(self, api_key=None):
            self.messages = MagicMock()

    fake_anthropic.Anthropic = _FakeAnthropicClient
    import sys
    monkeypatch.setitem(sys.modules, "anthropic", fake_anthropic)

    import importlib

    import wire.zc_search as mod
    importlib.reload(mod)
    return mod


def _fake_response():
    resp = MagicMock()
    resp.content = []
    resp.usage = MagicMock()
    resp.usage.model_dump = lambda: {}
    resp.stop_reason = "end_turn"
    return resp


def test_web_search_tool_bumped_to_v1_24_0_version(search_mod):
    assert search_mod.WEB_SEARCH_TOOL["type"] == "web_search_20260318"


def test_web_fetch_tool_bumped_to_v1_24_0_version(search_mod):
    assert search_mod.WEB_FETCH_TOOL["type"] == "web_fetch_20260318"


def test_search_response_inclusion_applied_to_enabled_tools(search_mod):
    sc = search_mod.SearchCoder(api_key="sk-test")
    sc.client.messages.create.return_value = _fake_response()

    sc.search("q", web_search=True, web_fetch=True, response_inclusion="excluded")

    _, kwargs = sc.client.messages.create.call_args
    tools = kwargs["tools"]
    web_search = next(t for t in tools if t["name"] == "web_search")
    web_fetch = next(t for t in tools if t["name"] == "web_fetch")
    assert web_search["response_inclusion"] == "excluded"
    assert web_fetch["response_inclusion"] == "excluded"


def test_search_response_inclusion_omitted_by_default(search_mod):
    sc = search_mod.SearchCoder(api_key="sk-test")
    sc.client.messages.create.return_value = _fake_response()

    sc.search("q", web_search=True, web_fetch=False)

    _, kwargs = sc.client.messages.create.call_args
    assert "response_inclusion" not in kwargs["tools"][0]


def test_search_still_sets_max_uses_on_web_search(search_mod):
    sc = search_mod.SearchCoder(api_key="sk-test")
    sc.client.messages.create.return_value = _fake_response()

    sc.search("q", web_search=True, max_searches=7)

    _, kwargs = sc.client.messages.create.call_args
    assert kwargs["tools"][0]["max_uses"] == 7
