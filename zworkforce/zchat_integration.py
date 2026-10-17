"""Read-only, authenticated ZChat capability negotiation for zWorkforce."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

PROTOCOL = "zchat-zworkforce"
PROTOCOL_VERSION = "1.0"
CAPABILITIES_PATH = "/api/v1/integrations/zworkforce/v1/capabilities"
HEALTH_PATH = "/api/v1/integrations/zworkforce/v1/health"
MAX_RESPONSE_BYTES = 65_536
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._~-]{32,512}$")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _fetch(settings: Any, path: str, *, query: str = "") -> Any:
    """Fetch one fixed read-only v1 resource from a configured ZChat origin."""
    base_url = str(getattr(settings, "zchat_control_url", "") or "").strip()
    token = str(getattr(settings, "zchat_integration_token", "") or "").strip()
    if not base_url or not token:
        raise ValueError("ZChat integration is not configured")
    if not TOKEN_PATTERN.fullmatch(token):
        raise ValueError("ZChat integration token has an invalid format")

    try:
        parsed = urllib.parse.urlsplit(base_url)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        local_http = parsed.scheme == "http" and hostname in {
            "localhost",
            "127.0.0.1",
            "::1",
        }
        if (
            parsed.scheme != "https"
            and not local_http
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError(
                "ZChat control URL must be an HTTPS origin (HTTP is loopback-only)"
            )
        # Accessing .port validates malformed/out-of-range ports.
        if parsed.port == 0:
            raise ValueError("ZChat control URL has an invalid port")
    except ValueError as exc:
        if str(exc).startswith("ZChat control URL"):
            raise
        raise ValueError("ZChat control URL is invalid") from None

    endpoint = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, query, ""))
    request = urllib.request.Request(
        endpoint,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="GET",
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=5) as response:
            if 300 <= response.status < 400:
                raise ValueError("ZChat integration redirects are rejected")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise ValueError(
            f"ZChat integration request failed with HTTP {exc.code}"
        ) from None
    except ValueError:
        raise
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ValueError("ZChat integration request failed") from None

    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("ZChat integration response exceeds the size limit")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("ZChat integration response is not valid JSON") from None
    return payload


def fetch_capabilities(settings: Any) -> dict[str, Any]:
    """Fetch and validate the read-only v1 contract from a configured ZChat origin."""
    payload = _fetch(settings, CAPABILITIES_PATH)
    _validate_capabilities(payload)
    return payload


def fetch_resource(settings: Any, resource: str) -> dict[str, str]:
    """Fetch the sole non-account-scoped health resource."""
    if resource != "health":
        raise ValueError("Unsupported ZChat integration resource")
    payload = _fetch(settings, HEALTH_PATH)
    if not isinstance(payload, dict) or set(payload) != {"status", "database"}:
        raise TypeError("ZChat health response has an invalid schema")
    if any(not isinstance(value, str) for value in payload.values()):
        raise TypeError("ZChat health fields must be strings")
    if payload != {"status": "healthy", "database": "reachable"}:
        raise ValueError("ZChat health response reports an unsupported state")
    return payload


def _validate_capabilities(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise TypeError("ZChat capability response must be an object")
    expected_fields = {
        "protocol",
        "protocol_version",
        "compatible_versions",
        "server_version",
        "read_only_resources",
        "features",
    }
    if set(payload) != expected_fields:
        raise ValueError("ZChat capability response has an incompatible schema")
    compatible_versions = payload.get("compatible_versions")
    if not isinstance(compatible_versions, list) or any(
        not isinstance(version, str) for version in compatible_versions
    ):
        raise TypeError("ZChat compatible_versions must be a string array")
    if any(
        not version or version != version.strip() for version in compatible_versions
    ):
        raise ValueError(
            "ZChat compatible_versions must contain non-empty trimmed values"
        )
    if len(compatible_versions) != len(set(compatible_versions)):
        raise ValueError("ZChat compatible_versions must be unique")
    if (
        payload.get("protocol") != PROTOCOL
        or payload.get("protocol_version") != PROTOCOL_VERSION
        or PROTOCOL_VERSION not in compatible_versions
    ):
        raise ValueError("ZChat integration protocol version is incompatible")
    server_version = payload.get("server_version")
    if not isinstance(server_version, str) or not server_version.strip():
        raise TypeError(
            "ZChat capability response server_version must be a non-empty string"
        )
    resources = payload.get("read_only_resources")
    if not isinstance(resources, list) or any(
        not isinstance(resource, str) for resource in resources
    ):
        raise TypeError("ZChat read_only_resources must be a string array")
    if any(not resource or resource != resource.strip() for resource in resources):
        raise ValueError(
            "ZChat read_only_resources must contain non-empty trimmed values"
        )
    if len(resources) != len(set(resources)):
        raise ValueError("ZChat read_only_resources must be unique")
    if set(resources) != {"health", "capabilities"}:
        raise ValueError(
            "ZChat v1 must expose the health and capabilities read-only resources"
        )
    features = payload.get("features")
    if not isinstance(features, list):
        raise TypeError("ZChat capability response features must be an array")

    boolean_fields = (
        "standalone_supported",
        "unified_supported",
        "requires_provider_client",
        "supports_offline",
        "supports_read_only",
        "supports_strict_background",
        "supports_minimized_client",
        "supports_hidden_client",
        "supports_remote_commands",
        "supports_external_outcome_verification",
        "requires_exclusive_resource",
    )
    feature_fields = {
        "feature_id",
        "provider",
        *boolean_fields,
        "verified_platforms",
        "verified_provider_versions",
        "implementation_status",
        "evidence_status",
    }
    feature_ids: set[str] = set()
    for feature in features:
        if not isinstance(feature, dict):
            raise TypeError("ZChat capability feature must be an object")
        if set(feature) != feature_fields:
            raise ValueError("ZChat capability feature has an incompatible schema")
        feature_id = feature.get("feature_id")
        provider = feature.get("provider")
        if (
            not isinstance(feature_id, str)
            or not feature_id.strip()
            or feature_id != feature_id.strip()
            or not isinstance(provider, str)
            or not provider.strip()
            or provider != provider.strip()
        ):
            raise TypeError(
                "ZChat capability feature identity must use non-empty strings"
            )
        if feature_id in feature_ids:
            raise ValueError("ZChat capability feature IDs must be unique")
        feature_ids.add(feature_id)
        if any(type(feature.get(field)) is not bool for field in boolean_fields):
            raise TypeError("ZChat capability feature flags must be booleans")
        for field in ("verified_platforms", "verified_provider_versions"):
            values = feature.get(field)
            if not isinstance(values, list) or any(
                not isinstance(value, str) for value in values
            ):
                raise TypeError(
                    f"ZChat capability feature field {field} must be a string array"
                )
            if any(not value or value != value.strip() for value in values):
                raise ValueError(
                    f"ZChat capability feature field {field} must contain non-empty trimmed values"
                )
            if len(values) != len(set(values)):
                raise ValueError(
                    f"ZChat capability feature field {field} must be unique"
                )
        for field in ("implementation_status", "evidence_status"):
            value = feature.get(field)
            if not isinstance(value, str) or not value.strip():
                raise TypeError(
                    f"ZChat capability feature field {field} must be a non-empty string"
                )
