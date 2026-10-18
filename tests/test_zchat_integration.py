from __future__ import annotations

import json
import threading
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from zworkforce.config import Settings
from zworkforce.zchat_integration import (
    CAPABILITIES_PATH,
    fetch_capabilities,
    fetch_resource,
)


def _capability_document(*, version: str = "1.0") -> dict:
    feature_ids = (
        "camfrog.room_control",
        "camfrog.private_chat",
        "camfrog.status_random",
        "camfrog.status_marquee",
        "camfrog.im_autoreply",
        "camfrog.web_status",
        "camfrog.music_dj",
        "camfrog.status_changer",
        "line.status_changer",
    )
    return {
        "protocol": "zchat-zworkforce",
        "protocol_version": version,
        "compatible_versions": [version],
        "server_version": "0.1.0",
        "read_only_resources": ["health", "capabilities"],
        "features": [
            {
                "feature_id": feature_id,
                "provider": "line" if feature_id.startswith("line.") else "camfrog",
                "standalone_supported": True,
                "unified_supported": feature_id
                in {
                    "camfrog.private_chat",
                    "camfrog.status_random",
                    "camfrog.status_marquee",
                    "camfrog.status_changer",
                },
                "requires_provider_client": feature_id != "camfrog.web_status",
                "supports_offline": False,
                "supports_read_only": feature_id == "camfrog.private_chat",
                "supports_strict_background": False,
                "supports_minimized_client": False,
                "supports_hidden_client": False,
                "supports_remote_commands": False,
                "supports_external_outcome_verification": False,
                "requires_exclusive_resource": True,
                "verified_platforms": [],
                "verified_provider_versions": [],
                "implementation_status": "implemented",
                "evidence_status": "PARTIALLY VERIFIED",
            }
            for feature_id in feature_ids
        ],
    }


class _Server:
    def __init__(
        self, *, payload: dict | None = None, status: int = 200, redirect: str = ""
    ):
        self.authorization = ""
        self.path = ""
        self.payload = payload or _capability_document()
        self.status = status
        self.redirect = redirect
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                owner.authorization = self.headers.get("Authorization", "")
                owner.path = self.path
                self.send_response(owner.status)
                if owner.redirect:
                    self.send_header("Location", owner.redirect)
                    self.end_headers()
                    return
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(owner.payload).encode())

            def log_message(self, *_args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"


def _settings(url: str, token: str = "z" * 48) -> Settings:
    return replace(Settings(), zchat_control_url=url, zchat_integration_token=token)


def test_fetch_capabilities_uses_authenticated_versioned_read_only_endpoint():
    with _Server() as server:
        result = fetch_capabilities(_settings(server.url))

    assert server.path == CAPABILITIES_PATH
    assert server.authorization == f"Bearer {'z' * 48}"
    assert result["protocol_version"] == "1.0"
    assert result["features"][0]["supports_external_outcome_verification"] is False
    assert len(result["features"]) == 9
    assert (
        next(
            feature
            for feature in result["features"]
            if feature["feature_id"] == "camfrog.status_changer"
        )["unified_supported"]
        is True
    )
    assert all(
        feature["unified_supported"] is True
        for feature in result["features"]
        if feature["feature_id"] in {"camfrog.status_random", "camfrog.status_marquee"}
    )
    assert (
        next(
            feature
            for feature in result["features"]
            if feature["feature_id"] == "camfrog.private_chat"
        )["supports_read_only"]
        is True
    )
    assert all(
        feature["unified_supported"] is False
        for feature in result["features"]
        if feature["feature_id"]
        not in {
            "camfrog.status_random",
            "camfrog.status_marquee",
            "camfrog.status_changer",
            "camfrog.private_chat",
        }
    )
    assert all(
        feature["supports_remote_commands"] is False for feature in result["features"]
    )


def test_fetch_capabilities_fails_closed_when_not_configured():
    with pytest.raises(ValueError, match="not configured"):
        fetch_capabilities(Settings())


def test_integration_token_is_excluded_from_settings_repr():
    token = "z" * 48
    settings = _settings("https://control.example.test", token)

    assert token not in repr(settings)


def test_fetch_capabilities_rejects_non_loopback_http():
    with pytest.raises(ValueError, match="HTTPS origin"):
        fetch_capabilities(_settings("http://control.example.com"))


def test_fetch_capabilities_rejects_redirects():
    with (
        _Server(status=302, redirect="http://127.0.0.1:1/collect") as server,
        pytest.raises(ValueError, match="HTTP 302"),
    ):
        fetch_capabilities(_settings(server.url))


def test_fetch_capabilities_rejects_incompatible_protocol():
    with (
        _Server(payload=_capability_document(version="2.0")) as server,
        pytest.raises(ValueError, match="incompatible"),
    ):
        fetch_capabilities(_settings(server.url))


def test_fetch_capabilities_rejects_non_boolean_claims():
    payload = _capability_document()
    payload["features"][0]["supports_hidden_client"] = "unknown"
    with (
        _Server(payload=payload) as server,
        pytest.raises(TypeError, match="must be booleans"),
    ):
        fetch_capabilities(_settings(server.url))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("implementation_status", "production-ready"),
        ("evidence_status", "verified-ish"),
    ],
)
def test_fetch_capabilities_rejects_noncanonical_status_claims(field, value):
    payload = _capability_document()
    payload["features"][0][field] = value
    with (
        _Server(payload=payload) as server,
        pytest.raises(ValueError, match=f"{field} is not a recognized v1 state"),
    ):
        fetch_capabilities(_settings(server.url))


def test_fetch_capabilities_rejects_remote_command_claims_in_read_only_v1():
    payload = _capability_document()
    payload["features"][0]["supports_remote_commands"] = True
    with (
        _Server(payload=payload) as server,
        pytest.raises(ValueError, match="does not support remote commands"),
    ):
        fetch_capabilities(_settings(server.url))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("implementation_status", None),
        ("implementation_status", " "),
        ("evidence_status", None),
        ("evidence_status", ""),
    ],
)
def test_fetch_capabilities_rejects_missing_or_empty_evidence_labels(field, value):
    payload = _capability_document()
    payload["features"][0][field] = value
    with (
        _Server(payload=payload) as server,
        pytest.raises(TypeError, match=f"{field} must be a non-empty string"),
    ):
        fetch_capabilities(_settings(server.url))


def test_fetch_capabilities_rejects_ambiguous_duplicate_feature_ids():
    payload = _capability_document()
    payload["features"].append(payload["features"][0].copy())
    with (
        _Server(payload=payload) as server,
        pytest.raises(ValueError, match="feature IDs must be unique"),
    ):
        fetch_capabilities(_settings(server.url))


def test_fetch_capabilities_rejects_unrecognized_fields_instead_of_forwarding_them():
    payload = _capability_document()
    payload["integration_token"] = "must-not-reach-mcp"
    with (
        _Server(payload=payload) as server,
        pytest.raises(ValueError, match="incompatible schema"),
    ):
        fetch_capabilities(_settings(server.url))


def test_fetch_capabilities_rejects_unrecognized_feature_fields():
    payload = _capability_document()
    payload["features"][0]["account_token"] = "must-not-reach-mcp"
    with (
        _Server(payload=payload) as server,
        pytest.raises(ValueError, match="feature has an incompatible schema"),
    ):
        fetch_capabilities(_settings(server.url))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("compatible_versions", ["1.0", "1.0"], "compatible_versions must be unique"),
        ("compatible_versions", ["1.0", " "], "non-empty trimmed values"),
        (
            "read_only_resources",
            ["health", "health"],
            "read_only_resources must be unique",
        ),
        ("read_only_resources", [" "], "non-empty trimmed values"),
    ],
)
def test_fetch_capabilities_rejects_ambiguous_contract_lists(field, value, message):
    payload = _capability_document()
    payload[field] = value
    with _Server(payload=payload) as server, pytest.raises(ValueError, match=message):
        fetch_capabilities(_settings(server.url))


@pytest.mark.parametrize(
    "resources",
    [[], ["health"], ["health", "capabilities", "accounts"]],
)
def test_fetch_capabilities_requires_the_current_zchat_read_only_resources(resources):
    payload = _capability_document()
    payload["read_only_resources"] = resources
    with (
        _Server(payload=payload) as server,
        pytest.raises(ValueError, match="health and capabilities"),
    ):
        fetch_capabilities(_settings(server.url))


def test_fetch_resource_accepts_only_the_v1_healthy_state():
    health = {"status": "healthy", "database": "reachable"}
    with _Server(payload=health) as server:
        assert fetch_resource(_settings(server.url), "health") == health

    unhealthy = {"status": "degraded", "database": "unreachable"}
    with (
        _Server(payload=unhealthy) as server,
        pytest.raises(ValueError, match="unsupported state"),
    ):
        fetch_resource(_settings(server.url), "health")
