from __future__ import annotations

import hashlib
import json
import re
from typing import Any


CAPABILITY_API_VERSION = "zworkforce.ai/v1"
CAPABILITY_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
SHA256_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
HOSTNAME = re.compile(
    r"^(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$"
)

CAPABILITY_KINDS = {
    "Prompt",
    "Skill",
    "Agent",
    "MCPServer",
    "Workflow",
    "KnowledgePack",
    "EvaluationPack",
    "PolicyPack",
    "Automation",
}
VISIBILITY_LEVELS = {
    "private": 0,
    "tenant": 1,
    "organization": 2,
    "public": 3,
}
VISIBILITIES = set(VISIBILITY_LEVELS)
MUTABILITIES = {"read_only", "mutating"}
RISK_LEVELS = {f"R{level}": level for level in range(6)}
NETWORK_MODES = {"deny", "allowlist", "platform"}


class CapabilityError(ValueError):
    pass


def is_enterprise_manifest(manifest: dict[str, Any]) -> bool:
    return bool(manifest.get("apiVersion") or manifest.get("kind"))


def canonical_capability(manifest: dict[str, Any]) -> bytes:
    validate_capability_manifest(manifest)
    return json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def capability_fingerprint(manifest: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_capability(manifest)).hexdigest()


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() or item != item.strip()
        for item in value
    ):
        raise CapabilityError(f"{field} must be an array of canonical non-empty strings")
    if len(value) != len(set(value)):
        raise CapabilityError(f"{field} must not contain duplicates")
    return value


def _validate_metadata(manifest: dict[str, Any]) -> None:
    metadata = manifest.get("metadata")
    if not isinstance(metadata, dict):
        raise CapabilityError("metadata must be an object")
    owner = metadata.get("owner")
    if (
        not isinstance(owner, str)
        or not owner.strip()
        or owner != owner.strip()
        or len(owner) > 200
    ):
        raise CapabilityError(
            "metadata.owner is required, canonical, and must be <= 200 characters"
        )
    visibility = metadata.get("visibility")
    if visibility not in VISIBILITIES:
        raise CapabilityError(
            f"metadata.visibility must be one of {sorted(VISIBILITIES)}"
        )


def _validate_permissions(manifest: dict[str, Any]) -> None:
    permissions = manifest.get("permissions")
    if not isinstance(permissions, dict):
        raise CapabilityError("permissions must be an object")
    tools = _string_list(permissions.get("tools", []), "permissions.tools")
    _string_list(permissions.get("scopes", []), "permissions.scopes")
    _string_list(permissions.get("secrets", []), "permissions.secrets")

    allowed_tools = manifest.get("allowed_tools")
    if allowed_tools is not None:
        legacy_tools = _string_list(allowed_tools, "allowed_tools")
        if set(legacy_tools) != set(tools):
            raise CapabilityError("allowed_tools must exactly match permissions.tools")


def _validate_approval_and_risk(manifest: dict[str, Any]) -> None:
    mutability = manifest.get("mutability")
    if mutability not in MUTABILITIES:
        raise CapabilityError(f"mutability must be one of {sorted(MUTABILITIES)}")

    security = manifest.get("security")
    if not isinstance(security, dict):
        raise CapabilityError("security must be an object")
    risk = security.get("risk")
    if risk not in RISK_LEVELS:
        raise CapabilityError("security.risk must be R0 through R5")

    approval = manifest.get("approval")
    if not isinstance(approval, dict):
        raise CapabilityError("approval must be an object")
    required = approval.get("required")
    minimum = approval.get("minimum_approvals")
    if not isinstance(required, bool):
        raise CapabilityError("approval.required must be a boolean")
    if (
        not isinstance(minimum, int)
        or isinstance(minimum, bool)
        or minimum < 0
        or minimum > 10
    ):
        raise CapabilityError(
            "approval.minimum_approvals must be an integer from 0 to 10"
        )
    if required and minimum < 1:
        raise CapabilityError(
            "approval.minimum_approvals must be >= 1 when approval is required"
        )
    if not required and minimum != 0:
        raise CapabilityError(
            "approval.minimum_approvals must be 0 when approval is not required"
        )
    if mutability == "mutating" and not required:
        raise CapabilityError("mutating capabilities require approval")
    if RISK_LEVELS[risk] >= 3 and not required:
        raise CapabilityError("R3-R5 capabilities require approval")


def _validate_network(manifest: dict[str, Any]) -> None:
    network = manifest.get("network")
    if not isinstance(network, dict):
        raise CapabilityError("network must be an object")
    mode = network.get("mode")
    if mode not in NETWORK_MODES:
        raise CapabilityError(f"network.mode must be one of {sorted(NETWORK_MODES)}")
    hosts = _string_list(network.get("allowed_hosts", []), "network.allowed_hosts")
    if mode != "allowlist" and hosts:
        raise CapabilityError("network.allowed_hosts is only valid with allowlist mode")
    if mode == "allowlist" and not hosts:
        raise CapabilityError("allowlist network mode requires at least one host")
    for host in hosts:
        if host.startswith("*.") or not HOSTNAME.fullmatch(host):
            raise CapabilityError(
                "network.allowed_hosts must contain exact DNS hostnames without wildcards"
            )


def _bounded_int(value: Any, field: str, minimum: int, maximum: int) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not minimum <= value <= maximum
    ):
        raise CapabilityError(f"{field} must be an integer from {minimum} to {maximum}")
    return value


def _validate_resources(manifest: dict[str, Any]) -> None:
    resources = manifest.get("resources")
    if not isinstance(resources, dict):
        raise CapabilityError("resources must be an object")
    _bounded_int(
        resources.get("timeout_seconds"),
        "resources.timeout_seconds",
        1,
        3600,
    )
    _bounded_int(resources.get("memory_mb"), "resources.memory_mb", 64, 32768)
    _bounded_int(resources.get("cpu_millis"), "resources.cpu_millis", 10, 8000)


def _validate_provenance(manifest: dict[str, Any]) -> None:
    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        raise CapabilityError("provenance must be an object")
    source = provenance.get("source")
    digest = provenance.get("digest")
    if (
        not isinstance(source, str)
        or not source.strip()
        or source != source.strip()
        or len(source) > 500
    ):
        raise CapabilityError(
            "provenance.source is required, canonical, and must be <= 500 characters"
        )
    if not isinstance(digest, str) or not SHA256_DIGEST.fullmatch(digest):
        raise CapabilityError(
            "provenance.digest must be a lowercase sha256:<64 hex> digest"
        )


def _validate_evaluation(manifest: dict[str, Any]) -> None:
    evaluation = manifest.get("evaluation")
    if evaluation is None:
        return
    if not isinstance(evaluation, dict):
        raise CapabilityError("evaluation must be an object")
    suite = evaluation.get("suite")
    score = evaluation.get("minimum_score")
    if (
        not isinstance(suite, str)
        or not suite.strip()
        or suite != suite.strip()
        or len(suite) > 200
    ):
        raise CapabilityError("evaluation.suite must be a canonical non-empty string")
    if (
        not isinstance(score, (int, float))
        or isinstance(score, bool)
        or not 0 <= float(score) <= 1
    ):
        raise CapabilityError("evaluation.minimum_score must be between 0 and 1")


def validate_capability_manifest(
    manifest: dict[str, Any],
    *,
    expected_kind: str | None = None,
) -> None:
    if not isinstance(manifest, dict):
        raise CapabilityError("capability manifest must be an object")
    if manifest.get("apiVersion") != CAPABILITY_API_VERSION:
        raise CapabilityError(f"apiVersion must be {CAPABILITY_API_VERSION}")
    kind = manifest.get("kind")
    if kind not in CAPABILITY_KINDS:
        raise CapabilityError(f"kind must be one of {sorted(CAPABILITY_KINDS)}")
    if expected_kind is not None and kind != expected_kind:
        raise CapabilityError(f"kind must be {expected_kind}")

    capability_id = manifest.get("id")
    if not isinstance(capability_id, str) or not CAPABILITY_ID.fullmatch(capability_id):
        raise CapabilityError("id must be a DNS-like slug")
    version = manifest.get("version")
    if not isinstance(version, str) or not version or len(version) > 64:
        raise CapabilityError("version is required and must be <= 64 characters")

    _validate_metadata(manifest)
    _validate_permissions(manifest)
    _validate_approval_and_risk(manifest)
    _validate_network(manifest)
    _validate_resources(manifest)
    _validate_provenance(manifest)
    _validate_evaluation(manifest)


def _authority_view(manifest: dict[str, Any]) -> dict[str, Any]:
    if is_enterprise_manifest(manifest):
        validate_capability_manifest(manifest)
        permissions = manifest["permissions"]
        approval = manifest["approval"]
        resources = manifest["resources"]
        network = manifest["network"]
        evaluation = manifest.get("evaluation")
        return {
            "kind": manifest["kind"],
            "id": manifest["id"],
            "owner": manifest["metadata"]["owner"],
            "visibility": VISIBILITY_LEVELS[manifest["metadata"]["visibility"]],
            "tools": set(permissions.get("tools", [])),
            "scopes": set(permissions.get("scopes", [])),
            "secrets": set(permissions.get("secrets", [])),
            "mutability": manifest["mutability"],
            "approval_required": approval["required"],
            "minimum_approvals": approval["minimum_approvals"],
            "risk": RISK_LEVELS[manifest["security"]["risk"]],
            "network_mode": network["mode"],
            "hosts": set(network.get("allowed_hosts", [])),
            "timeout_seconds": resources["timeout_seconds"],
            "memory_mb": resources["memory_mb"],
            "cpu_millis": resources["cpu_millis"],
            "evaluation_suite": evaluation.get("suite") if evaluation else None,
            "evaluation_score": (
                float(evaluation["minimum_score"]) if evaluation else None
            ),
        }

    return {
        "kind": "Skill",
        "id": manifest.get("id"),
        "owner": None,
        "visibility": 0,
        "tools": set(manifest.get("allowed_tools", [])),
        "scopes": set(),
        "secrets": set(),
        "mutability": "read_only",
        "approval_required": False,
        "minimum_approvals": 0,
        "risk": 0,
        "network_mode": "deny",
        "hosts": set(),
        "timeout_seconds": 3600,
        "memory_mb": 32768,
        "cpu_millis": 8000,
        "evaluation_suite": None,
        "evaluation_score": None,
    }


def assert_safe_capability_upgrade(
    current: dict[str, Any],
    candidate: dict[str, Any],
) -> None:
    old = _authority_view(current)
    new = _authority_view(candidate)

    if old["id"] != new["id"] or old["kind"] != new["kind"]:
        raise CapabilityError(
            "automatic upgrade cannot change capability identity or kind"
        )
    if old["owner"] is not None and new["owner"] != old["owner"]:
        raise CapabilityError("automatic upgrade cannot transfer capability ownership")
    if new["visibility"] > old["visibility"]:
        raise CapabilityError("automatic upgrade cannot broaden capability visibility")
    if not new["tools"] <= old["tools"]:
        raise CapabilityError("automatic upgrade cannot add tool permissions")
    if not new["scopes"] <= old["scopes"]:
        raise CapabilityError("automatic upgrade cannot add authorization scopes")
    if not new["secrets"] <= old["secrets"]:
        raise CapabilityError("automatic upgrade cannot add secret access")
    if old["mutability"] == "read_only" and new["mutability"] == "mutating":
        raise CapabilityError(
            "automatic upgrade cannot escalate read-only capability to mutating"
        )
    if old["approval_required"] and not new["approval_required"]:
        raise CapabilityError("automatic upgrade cannot remove an approval requirement")
    if new["minimum_approvals"] < old["minimum_approvals"]:
        raise CapabilityError("automatic upgrade cannot reduce required approvals")
    if new["risk"] < old["risk"]:
        raise CapabilityError("automatic upgrade cannot silently lower declared risk")

    if new["network_mode"] != old["network_mode"]:
        if new["network_mode"] != "deny":
            raise CapabilityError("automatic upgrade cannot change network authority mode")
    elif old["network_mode"] == "allowlist" and not new["hosts"] <= old["hosts"]:
        raise CapabilityError("automatic upgrade cannot expand network access")

    if new["timeout_seconds"] > old["timeout_seconds"]:
        raise CapabilityError("automatic upgrade cannot increase execution timeout")
    if new["memory_mb"] > old["memory_mb"]:
        raise CapabilityError("automatic upgrade cannot increase memory authority")
    if new["cpu_millis"] > old["cpu_millis"]:
        raise CapabilityError("automatic upgrade cannot increase CPU authority")

    if old["evaluation_suite"] is not None:
        if new["evaluation_suite"] is None:
            raise CapabilityError("automatic upgrade cannot remove evaluation requirements")
        if new["evaluation_suite"] != old["evaluation_suite"]:
            raise CapabilityError("automatic upgrade cannot change the evaluation suite")
        if new["evaluation_score"] < old["evaluation_score"]:
            raise CapabilityError("automatic upgrade cannot lower the evaluation threshold")
