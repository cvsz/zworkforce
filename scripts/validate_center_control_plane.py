#!/usr/bin/env python3
"""Semantic validation for the ZEAZ center-control-plane registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


class RegistryValidationError(ValueError):
    pass


def validate_registry(data: dict[str, Any]) -> None:
    if data.get("version") != 1:
        raise RegistryValidationError("unsupported registry version; expected 1")

    repositories = data.get("repositories")
    hostnames = data.get("hostnames")
    if not isinstance(repositories, list) or not isinstance(hostnames, dict):
        raise RegistryValidationError("repositories must be a list and hostnames must be an object")

    repo_by_name: dict[str, dict[str, Any]] = {}
    for repo in repositories:
        if not isinstance(repo, dict):
            raise RegistryValidationError("repository entries must be objects")
        name = repo.get("name")
        if not isinstance(name, str) or not name:
            raise RegistryValidationError("repository name is required")
        if name in repo_by_name:
            raise RegistryValidationError(f"duplicate repository: {name}")
        repo_by_name[name] = repo

    for hostname, record in hostnames.items():
        if not isinstance(record, dict):
            raise RegistryValidationError(f"hostname {hostname} must map to an object")

        app_repo = record.get("applicationRepository")
        edge_owner = record.get("edgeOwnerRepository")
        if app_repo not in repo_by_name:
            raise RegistryValidationError(
                f"{hostname}: applicationRepository {app_repo!r} is not declared"
            )
        owner_record = repo_by_name.get(edge_owner)
        if owner_record is None:
            raise RegistryValidationError(
                f"{hostname}: edgeOwnerRepository {edge_owner!r} is not declared"
            )
        if owner_record.get("edgeOwnership") is not True:
            raise RegistryValidationError(
                f"{hostname}: edgeOwnerRepository {edge_owner!r} does not declare edgeOwnership=true"
            )

        if record.get("desiredState") == "VERIFIED" or record.get("effectiveState") == "VERIFIED":
            evidence = record.get("evidence")
            if not isinstance(evidence, dict):
                raise RegistryValidationError(f"{hostname}: VERIFIED state requires evidence")
            if evidence.get("environment") != record.get("environment"):
                raise RegistryValidationError(
                    f"{hostname}: evidence environment must match hostname environment"
                )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "registry",
        nargs="?",
        default="examples/center-control-plane.example.json",
        type=Path,
    )
    args = parser.parse_args()
    data = json.loads(args.registry.read_text(encoding="utf-8"))
    validate_registry(data)
    print(f"CENTER-CONTROL-PLANE: VERIFIED {args.registry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
