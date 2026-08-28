"""tests/test_zc_tools.py

Covers zc_tools.py's v1.24.0 server tool version bumps
(code_execution_20260521, web_search_20260318, web_fetch_20260318) and
the new response_inclusion parameter — see
docs/36_upgrade_v1.24.0_audit_and_impl.md Finding 1.
"""
import json

import wire.zc_tools as mod
from wire.zc_tools import RETIRED_TOOL_VERSIONS, SERVER_TOOLS, ToolCoder
from typing import Optional


class _FakeResp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _install_fake_urlopen(monkeypatch, captured: dict, response_body: Optional[dict] = None):
    response_body = response_body or {"content": [], "usage": {}, "stop_reason": "end_turn"}

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode())
        return _FakeResp(json.dumps(response_body).encode())

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)


def test_server_tools_defaults_bumped_to_v1_24_0_versions():
    assert SERVER_TOOLS["web_search"]["type"] == "web_search_20260318"
    assert SERVER_TOOLS["web_fetch"]["type"] == "web_fetch_20260318"
    assert SERVER_TOOLS["code_execution"]["type"] == "code_execution_20260521"


def test_retired_tool_versions_tracks_v1_24_0_supersessions():
    assert RETIRED_TOOL_VERSIONS["web_search_20260209"]["replacement"] == "web_search_20260318"
    assert RETIRED_TOOL_VERSIONS["web_fetch_20250910"]["replacement"] == "web_fetch_20260318"
    assert RETIRED_TOOL_VERSIONS["code_execution_20260120"]["replacement"] == "code_execution_20260521"


def test_check_retired_tool_version_flags_previous_defaults():
    assert mod.check_retired_tool_version("code_execution_20260120") is not None
    assert mod.check_retired_tool_version("web_search_20260209") is not None
    assert mod.check_retired_tool_version("code_execution_20260521") is None  # current, not retired


def test_generate_with_server_tools_response_inclusion_applied(monkeypatch):
    captured = {}
    _install_fake_urlopen(monkeypatch, captured)
    tc = ToolCoder(api_key="sk-test")

    tc.generate_with_server_tools("do it", ["web_search", "web_fetch"],
                                  response_inclusion="excluded")

    tools = captured["body"]["tools"]
    web_search = next(t for t in tools if t["name"] == "web_search")
    web_fetch = next(t for t in tools if t["name"] == "web_fetch")
    assert web_search["response_inclusion"] == "excluded"
    assert web_fetch["response_inclusion"] == "excluded"


def test_generate_with_server_tools_response_inclusion_omitted_by_default(monkeypatch):
    captured = {}
    _install_fake_urlopen(monkeypatch, captured)
    tc = ToolCoder(api_key="sk-test")

    tc.generate_with_server_tools("do it", ["web_search"])

    tools = captured["body"]["tools"]
    assert "response_inclusion" not in tools[0]


def test_generate_with_server_tools_response_inclusion_not_applied_to_other_tools(monkeypatch):
    captured = {}
    _install_fake_urlopen(monkeypatch, captured)
    tc = ToolCoder(api_key="sk-test")

    tc.generate_with_server_tools("do it", ["code_execution"], response_inclusion="excluded")

    tools = captured["body"]["tools"]
    assert "response_inclusion" not in tools[0]


def test_generate_with_server_tools_uses_bumped_code_execution_version(monkeypatch):
    captured = {}
    _install_fake_urlopen(monkeypatch, captured)
    tc = ToolCoder(api_key="sk-test")

    tc.generate_with_server_tools("do it", ["code_execution"])

    assert captured["body"]["tools"][0]["type"] == "code_execution_20260521"
