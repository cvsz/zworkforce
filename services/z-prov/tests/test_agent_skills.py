from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
from zeaz_agent import LocalSkillLoader, SkillPackageError


def write_package(
    root: Path,
    *,
    name: str = "safe-reader",
    skill: bytes = b"# Safe reader\n\nRead [reference](references/guide.md).\n",
    extras: dict[str, bytes] | None = None,
    manifest_changes: dict | None = None,
) -> Path:
    package = root / name
    package.mkdir()
    resources = {"SKILL.md": skill, **(extras or {"references/guide.md": b"# Guide\n"})}
    manifest_resources = []
    for relative, content in resources.items():
        target = package / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        manifest_resources.append(
            {
                "path": relative,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    manifest = {
        "schema_version": "1",
        "name": name,
        "version": "1.2.3",
        "description": "Read safe local references.",
        "entrypoint": "SKILL.md",
        "resources": manifest_resources,
    }
    manifest.update(manifest_changes or {})
    (package / "skill-manifest.json").write_text(
        json.dumps(manifest, separators=(",", ":")),
        encoding="utf-8",
    )
    return package


def test_loads_versioned_hash_pinned_skill_and_resources(tmp_path: Path) -> None:
    write_package(tmp_path)

    loaded = LocalSkillLoader(tmp_path).load("safe-reader")

    assert loaded.manifest.schema_version == "1"
    assert loaded.manifest.version == "1.2.3"
    assert loaded.instructions.startswith("# Safe reader")
    assert loaded.resource("references/guide.md") == b"# Guide\n"


@pytest.mark.parametrize(
    ("name", "changes", "message"),
    [
        ("safe-reader", {"schema_version": "2"}, "schema"),
        ("safe-reader", {"name": "another"}, "does not match"),
        ("safe-reader", {"version": "latest"}, "schema"),
        ("../escape", {}, "invalid skill name"),
    ],
)
def test_manifest_version_and_name_fail_closed(
    tmp_path: Path,
    name: str,
    changes: dict,
    message: str,
) -> None:
    if name != "../escape":
        write_package(tmp_path, manifest_changes=changes)
    with pytest.raises(SkillPackageError, match=message):
        LocalSkillLoader(tmp_path).load(name)


@pytest.mark.parametrize("bad_path", ["../secret", "/absolute", "a\\b", ".hidden", "a//b"])
def test_resource_paths_reject_traversal_and_nonportable_forms(
    tmp_path: Path,
    bad_path: str,
) -> None:
    package = write_package(tmp_path)
    manifest_path = package / "skill-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["resources"][0]["path"] = bad_path
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SkillPackageError, match="schema"):
        LocalSkillLoader(tmp_path).load("safe-reader")


@pytest.mark.parametrize("mutation", ["size", "hash", "content"])
def test_resource_integrity_mismatch_is_rejected(tmp_path: Path, mutation: str) -> None:
    package = write_package(tmp_path)
    manifest_path = package / "skill-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if mutation == "size":
        manifest["resources"][0]["size"] += 1
    elif mutation == "hash":
        manifest["resources"][0]["sha256"] = "0" * 64
    else:
        (package / "SKILL.md").write_text("changed", encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SkillPackageError, match="size|checksum"):
        LocalSkillLoader(tmp_path).load("safe-reader")


def test_unlisted_extra_file_and_undeclared_reference_are_rejected(tmp_path: Path) -> None:
    package = write_package(tmp_path)
    (package / "extra.txt").write_text("extra", encoding="utf-8")
    with pytest.raises(SkillPackageError, match="exactly match"):
        LocalSkillLoader(tmp_path).load("safe-reader")

    (package / "extra.txt").unlink()
    (package / "SKILL.md").write_text("[secret](secret.txt)", encoding="utf-8")
    manifest_path = package / "skill-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    content = (package / "SKILL.md").read_bytes()
    manifest["resources"][0].update(
        size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(SkillPackageError, match="undeclared"):
        LocalSkillLoader(tmp_path).load("safe-reader")


def test_encoded_traversal_and_forbidden_uri_are_rejected(tmp_path: Path) -> None:
    for index, destination in enumerate(("%2e%2e/secret", "file:///etc/passwd")):
        root = tmp_path / str(index)
        root.mkdir()
        package = write_package(root, skill=f"[bad]({destination})".encode())
        manifest_path = package / "skill-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        content = (package / "SKILL.md").read_bytes()
        manifest["resources"][0].update(
            size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(SkillPackageError, match="invalid|forbidden"):
            LocalSkillLoader(root).load("safe-reader")


def test_symlinks_devices_invalid_utf8_and_nul_are_rejected(tmp_path: Path) -> None:
    target = tmp_path / "real-root"
    target.mkdir()
    root_link = tmp_path / "root-link"
    root_link.symlink_to(target, target_is_directory=True)
    with pytest.raises(SkillPackageError, match="real directory"):
        LocalSkillLoader(root_link)

    package = write_package(target)
    guide = package / "references" / "guide.md"
    guide.unlink()
    guide.symlink_to(package / "SKILL.md")
    with pytest.raises(SkillPackageError, match="regular|symlink"):
        LocalSkillLoader(target).load("safe-reader")

    guide.unlink()
    os.mkfifo(guide)
    with pytest.raises(SkillPackageError, match="regular"):
        LocalSkillLoader(target).load("safe-reader")

    for content, message in ((b"\xff", "UTF-8"), (b"bad\x00text", "NUL")):
        isolated = tmp_path / message
        isolated.mkdir()
        write_package(isolated, skill=content, extras={})
        with pytest.raises(SkillPackageError, match=message):
            LocalSkillLoader(isolated).load("safe-reader")


def test_size_and_resource_count_limits_are_enforced(tmp_path: Path) -> None:
    write_package(
        tmp_path,
        skill=b"x" * 300,
        extras={"one.txt": b"a" * 200, "two.txt": b"b" * 200},
    )
    with pytest.raises(SkillPackageError, match="size limit"):
        LocalSkillLoader(
            tmp_path,
            max_file_bytes=256,
            max_package_bytes=512,
        ).load("safe-reader")
    with pytest.raises(SkillPackageError, match="resource-count"):
        LocalSkillLoader(tmp_path, max_resources=2).load("safe-reader")


def test_loading_never_executes_declared_script(tmp_path: Path) -> None:
    marker = tmp_path / "executed"
    script = f"#!/bin/sh\ntouch '{marker}'\n".encode()
    write_package(
        tmp_path,
        skill=b"# Skill\n\nSee [script](scripts/action.sh).\n",
        extras={"scripts/action.sh": script},
    )
    (tmp_path / "safe-reader" / "scripts" / "action.sh").chmod(0o755)

    LocalSkillLoader(tmp_path).load("safe-reader")

    assert not marker.exists()
