#!/usr/bin/env python3
"""สร้างและตรวจ metadata อนุมัติสำหรับ Terraform plan ของ Cloudflare ที่บันทึกไว้"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path


DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
TARGET_KEYS = {
    "account_id",
    "zone_id",
    "tunnel_id",
    "workspace",
    "backend_type",
    "backend_identity",
    "configuration_sha256",
}
FEATURE_KEYS = {"zeaz_one_enabled", "zeaz_one_api_route_enabled"}
HEALTH_CHECK_KEYS = {
    "zeaz_one_origin",
    "zeaz_one_hostname",
    "zeaz_one_api_origin",
    "zeaz_one_api_hostname",
    "zeaz_one_support_origin",
    "zeaz_one_support_hostname",
}


def fail(message: str) -> None:
    raise SystemExit(message)


def read_private_regular_file(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        fail(f"Cannot safely open required file: {path} ({exc.strerror})")
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            fail(f"Required file must be regular: {path}")
        if info.st_mode & 0o077:
            fail(f"Required file must not be group/world accessible: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(descriptor)


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def require_clean_value(label: str, value: object) -> str:
    if not isinstance(value, str) or not value or any(
        ord(character) < 32 or ord(character) == 127 for character in value
    ):
        fail(f"{label} must be nonempty and contain no control characters")
    return value


def configuration_sha256(directory: Path, environment_file: Path) -> str:
    if not directory.is_dir() or directory.is_symlink():
        fail("Terraform configuration directory must be a regular directory")

    relevant_paths = []
    for path in directory.rglob("*"):
        relative = path.relative_to(directory)
        if relative.parts[0] == ".terraform":
            continue
        if not path.is_file():
            continue
        if path.name == ".terraform.lock.hcl" or path.name.endswith(
            (".tf", ".tf.json", ".tfvars", ".tfvars.json")
        ):
            if path.is_symlink():
                fail("Terraform configuration inputs must not be symlinks")
            relevant_paths.append(path)

    environment_bytes = read_private_regular_file(environment_file)
    digest = hashlib.sha256()
    for path in sorted(
        relevant_paths, key=lambda item: item.relative_to(directory).as_posix()
    ):
        relative_name = path.relative_to(directory).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative_name).to_bytes(8, "big"))
        digest.update(relative_name)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    environment_label = b"environment-file"
    digest.update(len(environment_label).to_bytes(8, "big"))
    digest.update(environment_label)
    digest.update(len(environment_bytes).to_bytes(8, "big"))
    digest.update(environment_bytes)
    return digest.hexdigest()


def plan_variable(plan: dict, name: str) -> object:
    try:
        return plan["variables"][name]["value"]
    except (KeyError, TypeError):
        fail(f"Terraform saved plan is missing the required variable: {name}")


def write_private_exclusive(path: Path, content: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        fail(f"Refusing to overwrite an existing plan manifest: {path}")
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(descriptor)
    finally:
        os.close(descriptor)


def create(args: argparse.Namespace) -> int:
    plan_path = Path(args.plan)
    manifest_path = Path(args.manifest)
    plan_bytes = read_private_regular_file(plan_path)
    try:
        plan = json.loads(sys.stdin.buffer.read())
    except (UnicodeDecodeError, json.JSONDecodeError):
        fail("Terraform plan JSON is invalid; refusing to create an approval manifest")

    account_id = require_clean_value(
        "Planned Cloudflare account ID", plan_variable(plan, "cloudflare_account_id")
    )
    zone_id = require_clean_value(
        "Planned Cloudflare zone ID", plan_variable(plan, "cloudflare_zone_id")
    )
    tunnel_id = require_clean_value(
        "Planned Cloudflare tunnel ID", plan_variable(plan, "cloudflare_tunnel_id")
    )
    if account_id != args.expected_account_id or zone_id != args.expected_zone_id:
        fail("Planned Cloudflare account or zone differs from the current environment")
    if tunnel_id != args.expected_tunnel_id:
        fail("Planned Cloudflare tunnel differs from the current environment")

    features = {
        "zeaz_one_enabled": plan_variable(plan, "enable_zeaz_one"),
        "zeaz_one_api_route_enabled": plan_variable(
            plan, "enable_zeaz_one_api_route"
        ),
    }
    if not all(isinstance(value, bool) for value in features.values()):
        fail("Terraform plan ZEAZ One feature flags must be booleans")
    health_checks = {
        "zeaz_one_origin": plan_variable(plan, "zeaz_one_origin"),
        "zeaz_one_hostname": plan_variable(plan, "zeaz_one_hostname"),
        "zeaz_one_api_origin": plan_variable(plan, "zeaz_one_api_origin"),
        "zeaz_one_api_hostname": plan_variable(plan, "zeaz_one_api_hostname"),
        "zeaz_one_support_origin": plan_variable(plan, "zeaz_one_support_origin"),
        "zeaz_one_support_hostname": plan_variable(plan, "zeaz_one_support_hostname"),
    }
    for key, value in health_checks.items():
        health_checks[key] = require_clean_value(f"Planned {key}", value)

    metadata = {
        "format_version": 1,
        "plan_sha256": sha256_bytes(plan_bytes),
        "target": {
            "account_id": account_id,
            "zone_id": zone_id,
            "tunnel_id": tunnel_id,
            "workspace": require_clean_value("Terraform workspace", args.workspace),
            "backend_type": require_clean_value("Terraform backend type", args.backend_type),
            "backend_identity": require_clean_value(
                "Terraform backend identity", args.backend_identity
            ),
            "configuration_sha256": configuration_sha256(
                Path(args.configuration_dir), Path(args.environment_file)
            ),
        },
        "features": features,
        "health_checks": health_checks,
    }
    approval_sha256 = sha256_bytes(canonical_json(metadata))
    document = {
        "metadata": metadata,
        "approval_sha256": approval_sha256,
    }
    content = (json.dumps(document, sort_keys=True, indent=2) + "\n").encode("utf-8")
    write_private_exclusive(manifest_path, content)
    print(approval_sha256)
    return 0


def verify(args: argparse.Namespace) -> int:
    if not DIGEST_PATTERN.fullmatch(args.expected_approval_sha256):
        fail("Expected approval SHA-256 must be 64 lowercase hexadecimal characters")

    plan_bytes = read_private_regular_file(Path(args.plan))
    manifest_bytes = read_private_regular_file(Path(args.manifest))
    try:
        document = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        fail("Saved plan manifest is not valid UTF-8 JSON")

    if not isinstance(document, dict) or set(document) != {"metadata", "approval_sha256"}:
        fail("Saved plan manifest has an unsupported structure")
    metadata = document["metadata"]
    if not isinstance(metadata, dict) or set(metadata) != {
        "format_version",
        "plan_sha256",
        "target",
        "features",
        "health_checks",
    }:
        fail("Saved plan manifest metadata has an unsupported structure")
    if type(metadata["format_version"]) is not int or metadata["format_version"] != 1:
        fail("Saved plan manifest format is not supported")
    if not isinstance(metadata["target"], dict) or set(metadata["target"]) != TARGET_KEYS:
        fail("Saved plan manifest target has an unsupported structure")
    if not isinstance(metadata["features"], dict) or set(metadata["features"]) != FEATURE_KEYS:
        fail("Saved plan manifest features have an unsupported structure")
    if not all(isinstance(value, bool) for value in metadata["features"].values()):
        fail("Saved plan manifest feature flags must be booleans")
    if not isinstance(metadata["health_checks"], dict) or set(metadata["health_checks"]) != HEALTH_CHECK_KEYS:
        fail("Saved plan manifest health checks have an unsupported structure")
    if not all(isinstance(value, str) for value in metadata["health_checks"].values()):
        fail("Saved plan manifest health check values must be strings")
    for key, value in metadata["health_checks"].items():
        require_clean_value(f"Saved plan {key}", value)

    plan_sha256 = sha256_bytes(plan_bytes)
    if metadata["plan_sha256"] != plan_sha256:
        fail("Saved plan SHA-256 does not match its approval manifest")
    computed_approval_sha256 = sha256_bytes(canonical_json(metadata))
    if document["approval_sha256"] != computed_approval_sha256:
        fail("Saved plan manifest approval digest is invalid")
    if args.expected_approval_sha256 != computed_approval_sha256:
        fail("Saved plan approval digest does not match; refusing to apply")

    expected_target = {
        "account_id": args.expected_account_id,
        "zone_id": args.expected_zone_id,
        "tunnel_id": args.expected_tunnel_id,
        "workspace": args.workspace,
        "backend_type": args.backend_type,
        "backend_identity": args.backend_identity,
        "configuration_sha256": configuration_sha256(
            Path(args.configuration_dir), Path(args.environment_file)
        ),
    }
    if metadata["target"] != expected_target:
        fail(
            "Saved plan target differs from the current account, zone, workspace, backend, environment, or Terraform configuration"
        )

    json.dump(metadata, sys.stdout, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    create_parser = commands.add_parser("create")
    create_parser.add_argument("--plan", required=True)
    create_parser.add_argument("--manifest", required=True)
    create_parser.add_argument("--configuration-dir", required=True)
    create_parser.add_argument("--environment-file", required=True)
    create_parser.add_argument("--expected-account-id", required=True)
    create_parser.add_argument("--expected-zone-id", required=True)
    create_parser.add_argument("--expected-tunnel-id", required=True)
    create_parser.add_argument("--workspace", required=True)
    create_parser.add_argument("--backend-type", required=True, choices=("local", "r2"))
    create_parser.add_argument("--backend-identity", required=True)
    create_parser.set_defaults(handler=create)

    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--plan", required=True)
    verify_parser.add_argument("--manifest", required=True)
    verify_parser.add_argument("--configuration-dir", required=True)
    verify_parser.add_argument("--environment-file", required=True)
    verify_parser.add_argument("--expected-account-id", required=True)
    verify_parser.add_argument("--expected-zone-id", required=True)
    verify_parser.add_argument("--expected-tunnel-id", required=True)
    verify_parser.add_argument("--workspace", required=True)
    verify_parser.add_argument("--backend-type", required=True, choices=("local", "r2"))
    verify_parser.add_argument("--backend-identity", required=True)
    verify_parser.add_argument("--expected-approval-sha256", required=True)
    verify_parser.set_defaults(handler=verify)

    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
