#!/usr/bin/env python3
"""Safely install the declarative ZEAZ agent/skill catalog.

Dry-run is the default. Files are copied only when --apply is supplied.
Existing destination files are never overwritten unless --overwrite is also set.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "configs" / "agent-skill-release-manifest.json"
AGENTS = ROOT / ".agents" / "agents"
SKILLS = ROOT / ".agents" / "skills"
SCHEMA = ROOT / "schemas" / "agent-skill-release-manifest.schema.json"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def safe_source(path: Path) -> Path:
    """Require source files to be regular files under ROOT with no symlinked path components."""
    root = ROOT.resolve()
    absolute_path = path.absolute()
    try:
        relative = absolute_path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"source path escapes repository: {path}") from exc

    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"refusing symlink source path: {current}")

    resolved = absolute_path.resolve()
    if resolved == root or root not in resolved.parents:
        raise ValueError(f"source path escapes repository: {path}")
    if not resolved.is_file():
        raise ValueError(f"source is not a regular file: {path}")
    return resolved


def catalog_files() -> list[tuple[Path, Path]]:
    manifest_path = safe_source(MANIFEST)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    agents_value = manifest.get("agents")
    skills_value = manifest.get("skills")
    if not isinstance(agents_value, list):
        raise ValueError("manifest.agents must be an array")
    if not isinstance(skills_value, list):
        raise ValueError("manifest.skills must be an array")

    result: list[tuple[Path, Path]] = []
    for name in agents_value:
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            raise ValueError(f"invalid agent identifier: {name!r}")
        source = safe_source(AGENTS / f"{name}.md")
        result.append((source, Path("agents") / source.name))
    for name in skills_value:
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            raise ValueError(f"invalid skill identifier: {name!r}")
        source = safe_source(SKILLS / name / "SKILL.md")
        result.append((source, Path("skills") / name / "SKILL.md"))
    result.extend([
        (manifest_path, Path("manifest.json")),
        (safe_source(SCHEMA), Path("manifest.schema.json")),
    ])
    return result


def safe_destination(root: Path, relative: Path) -> Path:
    """Reject path traversal, symlinked parents, and destinations outside root."""
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"invalid destination path: {relative}")

    resolved_root = root.resolve()
    destination = resolved_root / relative
    current = resolved_root
    for part in relative.parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"refusing symlink destination directory: {current}")
        if current.exists() and not current.is_dir():
            raise ValueError(f"destination parent is not a directory: {current}")

    if destination.is_symlink():
        raise ValueError(f"refusing symlink destination: {destination}")
    if destination.exists() and not destination.is_file():
        raise ValueError(f"destination is not a regular file: {destination}")

    resolved_parent = destination.parent.resolve()
    if resolved_parent != resolved_root and resolved_root not in resolved_parent.parents:
        raise ValueError(f"destination escapes target directory: {destination}")
    return destination



def validate_catalog_for_install() -> None:
    """Validate the manifest and referenced catalog files before any write."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if isinstance(manifest, dict):
        release = manifest.get("release")
        if isinstance(release, dict) and release.get("status") == "blocked":
            raise ValueError("refusing to install a blocked catalog release")

    validator_path = Path(__file__).resolve().with_name("validate_agent_skill_catalog.py")
    spec = importlib.util.spec_from_file_location("_agent_skill_catalog_validator", validator_path)
    if spec is None or spec.loader is None:
        raise ValueError("catalog validator could not be loaded")
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    validator.ROOT = ROOT
    validator.MANIFEST = MANIFEST
    validator.AGENT_DIR = AGENTS
    validator.SKILL_DIR = SKILLS
    errors = validator.validate()
    if errors:
        raise ValueError("catalog validation failed:\n- " + "\n- ".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True, help="Destination directory")
    parser.add_argument("--apply", action="store_true", help="Write files; otherwise only print the plan")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing existing regular files; requires --apply")
    args = parser.parse_args()

    if args.overwrite and not args.apply:
        parser.error("--overwrite requires --apply")

    try:
        files = catalog_files()
        validate_catalog_for_install()
        target = args.target.expanduser()
        if target.is_symlink():
            raise ValueError("target directory must not be a symlink")
        resolved_target = target.resolve()
        if resolved_target == ROOT or ROOT in resolved_target.parents:
            raise ValueError("target must not be inside the source repository")
        conflicts = []
        for _, relative in files:
            destination = safe_destination(resolved_target, relative)
            if destination.exists() and not args.overwrite:
                conflicts.append(str(destination))
        if conflicts:
            print("Installation blocked: destination files already exist (use --overwrite with --apply to replace):", file=sys.stderr)
            for item in conflicts:
                print(f"- {item}", file=sys.stderr)
            return 2

        print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
        print(f"Target: {resolved_target}")
        for source, relative in files:
            print(f"{'COPY' if args.apply else 'WOULD COPY'} {source.relative_to(ROOT)} -> {relative}")
        if not args.apply:
            print("Dry-run only; rerun with --apply to write files.")
            return 0

        resolved_target.mkdir(parents=True, exist_ok=True)
        for source, relative in files:
            destination = safe_destination(resolved_target, relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Re-check after directory creation to catch pre-existing or raced symlink paths.
            destination = safe_destination(resolved_target, relative)
            shutil.copyfile(source, destination)
        print(f"Installed {len(files)} files.")
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
