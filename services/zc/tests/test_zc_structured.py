"""tests/test_zc_structured.py

zc_structured.py had no prior test coverage. Added alongside the
v1.30.0 fix that removed the unconditional (and, since GA, unnecessary)
structured-outputs-2025-11-13 beta header and the dead, unused
StructuredCoder.BETA attribute — see docs/42_upgrade_v1.30.0.md.
"""
import json
from unittest.mock import patch

import wire.zc_structured as mod


def _fake_urlopen_json(payload_text):
    def _fake(req, timeout=120):
        return {"content": [{"type": "text", "text": payload_text}]}
    return _fake


def test_no_beta_header_sent_on_structured_request():
    sc = mod.StructuredCoder(api_key="sk-test")

    # Patch urlopen_json (imported into this module's namespace) to
    # capture the Request object _call() builds, without hitting the
    # network.
    captured_req = {}

    def _fake_urlopen_json(req, timeout=120):
        captured_req["headers"] = dict(req.headers)
        return {"content": [{"type": "text", "text": "{}"}]}

    with patch("wire.zc_structured.urlopen_json", _fake_urlopen_json):
        sc.json_object("say hi")

    headers = captured_req["headers"]
    # urllib.request.Request title-cases header keys it's given; check
    # case-insensitively for the deprecated beta header's absence.
    assert not any(k.lower() == "anthropic-beta" for k in headers), headers


def test_bare_class_has_no_dead_beta_attribute():
    assert not hasattr(mod.StructuredCoder, "BETA")


def test_json_object_still_uses_ga_output_config_format():
    sc = mod.StructuredCoder(api_key="sk-test")
    captured_req = {}

    def _fake_urlopen_json(req, timeout=120):
        captured_req["body"] = json.loads(req.data)
        return {"content": [{"type": "text", "text": '{"ok": true}'}]}

    with patch("wire.zc_structured.urlopen_json", _fake_urlopen_json):
        result = sc.json_object("say hi")

    assert captured_req["body"]["output_config"] == {"format": {"type": "json_object"}}
    assert result == {"ok": True}


def test_json_schema_mode_validates_required_fields():
    sc = mod.StructuredCoder(api_key="sk-test")
    schema = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}

    def _fake_urlopen_json(req, timeout=120):
        return {"content": [{"type": "text", "text": '{"name": "ok"}'}]}

    with patch("wire.zc_structured.urlopen_json", _fake_urlopen_json):
        result = sc.json_schema("extract the name", schema)

    assert result == {"name": "ok"}


def test_json_schema_mode_raises_on_missing_required_field():
    sc = mod.StructuredCoder(api_key="sk-test")
    schema = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}

    def _fake_urlopen_json(req, timeout=120):
        return {"content": [{"type": "text", "text": "{}"}]}

    with patch("wire.zc_structured.urlopen_json", _fake_urlopen_json):
        try:
            sc.json_schema("extract the name", schema)
            raise AssertionError("expected ValueError for missing required field")
        except ValueError as e:
            assert "name" in str(e)
