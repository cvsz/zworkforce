"""tests/test_zc_code_exec.py

Covers zc_code_exec.py, specifically the v1.22.0 drift fix: the
code_execution tool version bump from code_execution_20250522 (pre-GA,
required the code-execution-2025-05-22 beta header) to
code_execution_20260120 (GA, no beta header, REPL-state persistence) —
see docs/34_upgrade_v1.22.0_audit_and_impl.md Finding 4.

Exercises the real _call()/execute() path by monkeypatching
urllib.request.urlopen, per this repo's existing pattern in
tests/test_zc_compliance_api.py, rather than mocking urlopen_json
directly — this is what actually proves the anthropic-beta header is
(or isn't) sent on the wire.
"""
import json

import wire.zc_code_exec as mod
from wire.zc_code_exec import CodeExecutionCoder
from typing import Optional


class _FakeResp:
    def __init__(self, body: bytes):
        self._body = body
        self.headers: dict[str, str] = {}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _install_fake_urlopen(monkeypatch, captured_headers: dict, response_body: Optional[dict] = None):
    response_body = response_body or {"content": [], "usage": {}}

    def fake_urlopen(req, timeout=None):
        captured_headers.update(dict(req.headers))
        return _FakeResp(json.dumps(response_body).encode())

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)


def test_default_version_is_20260120():
    # DEFAULT_CODE_EXEC_VERSION was bumped to code_execution_20260521 in
    # v1.24.0; this assertion went stale then. Fixed while noticed during
    # the v1.26.0 cycle.
    assert mod.DEFAULT_CODE_EXEC_VERSION == "code_execution_20260521"
    assert mod.CODE_EXEC_TOOL["type"] == "code_execution_20260521"


def test_coder_defaults_to_20260120():
    coder = CodeExecutionCoder(api_key="sk-test")
    assert coder.code_exec_version == "code_execution_20260521"


def test_default_version_sends_no_beta_header(monkeypatch):
    captured = {}
    _install_fake_urlopen(monkeypatch, captured)
    coder = CodeExecutionCoder(api_key="sk-test")

    coder.execute("do something")

    # urllib.request.Request lower/title-cases header keys; check case-insensitively
    header_keys_lower = {k.lower() for k in captured}
    assert "anthropic-beta" not in header_keys_lower


def test_legacy_version_sends_beta_header(monkeypatch):
    captured = {}
    _install_fake_urlopen(monkeypatch, captured)
    coder = CodeExecutionCoder(api_key="sk-test", code_exec_version="code_execution_20250522")

    coder.execute("do something")

    header_map_lower = {k.lower(): v for k, v in captured.items()}
    assert header_map_lower.get("anthropic-beta") == "code-execution-2025-05-22"


def test_execute_uses_instance_version_in_tool_descriptor(monkeypatch):
    captured_payload = {}

    def fake_urlopen(req, timeout=None):
        captured_payload["body"] = json.loads(req.data.decode())
        return _FakeResp(json.dumps({"content": [], "usage": {}}).encode())

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    coder = CodeExecutionCoder(api_key="sk-test", code_exec_version="code_execution_20250522")

    coder.execute("do something")

    assert captured_payload["body"]["tools"] == [
        {"type": "code_execution_20250522", "name": "code_execution"}
    ]


def test_execute_block_parsing_unaffected_by_version(monkeypatch):
    """The wire format of tool_use/tool_result blocks is identical between
    the two tool versions — only the tool `type` string and beta header
    differ. Confirm execute()'s parsing logic still works with the new
    default version (regression check)."""
    response_body = {
        "content": [
            {"type": "text", "text": "Here is the result:"},
            {"type": "server_tool_use", "name": "code_execution",
             "input": {"code": "print(1+1)"}},
            {"type": "server_tool_result", "content": [
                {"type": "text", "text": "2\n"},
            ]},
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    captured = {}
    _install_fake_urlopen(monkeypatch, captured, response_body=response_body)
    coder = CodeExecutionCoder(api_key="sk-test")

    result = coder.execute("what is 1+1?")

    assert result["text"] == "Here is the result:"
    assert {"type": "executed_code", "code": "print(1+1)"} in result["outputs"]
    assert {"type": "stdout", "text": "2\n"} in result["outputs"]


def test_cmd_code_exec_threads_code_exec_version(monkeypatch, capsys):
    captured = {}
    _install_fake_urlopen(monkeypatch, captured)

    mod.cmd_code_exec("do something", api_key="sk-test", model="zc-xxx",
                      code_exec_version="code_execution_20250522")

    header_map_lower = {k.lower(): v for k, v in captured.items()}
    assert header_map_lower.get("anthropic-beta") == "code-execution-2025-05-22"
