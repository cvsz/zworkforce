import hashlib
import io
import json
import stat
import subprocess
import zipfile
from pathlib import Path
from uuid import UUID

import pytest
import zeaz_agent.plugins as plugin_module
from zeaz_agent.audit import JsonlAuditLog
from zeaz_agent.plugins import (
    OpenSSLEd25519Verifier,
    PluginArchiveReader,
    PluginAuditContext,
    PluginPackageError,
    PluginRegistry,
    PluginRegistryError,
)

SESSION_ID = UUID("00000000-0000-0000-0000-000000000001")
CORRELATION_ID = UUID("00000000-0000-0000-0000-000000000002")
AUDIT_CONTEXT = PluginAuditContext(
    session_id=SESSION_ID,
    correlation_id=CORRELATION_ID,
    actor="user:test",
)


class AcceptVerifier:
    def verify(self, payload: bytes, signature: bytes, key_id: str) -> None:
        assert payload
        assert signature == b"test"
        assert key_id == "test"


class ToggleAudit:
    def __init__(self, delegate: JsonlAuditLog) -> None:
        self.delegate = delegate
        self.fail = False

    def append(self, **kwargs):
        if self.fail:
            raise RuntimeError("audit unavailable")
        return self.delegate.append(**kwargs)


@pytest.fixture(scope="module")
def signing_keys(tmp_path_factory):
    root = tmp_path_factory.mktemp("plugin-signing")
    private = root / "private.pem"
    public = root / "public.pem"
    subprocess.run(
        (
            "/usr/bin/openssl",
            "genpkey",
            "-algorithm",
            "ED25519",
            "-out",
            str(private),
        ),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        (
            "/usr/bin/openssl",
            "pkey",
            "-in",
            str(private),
            "-pubout",
            "-out",
            str(public),
        ),
        check=True,
        capture_output=True,
    )
    return private, public.read_bytes()


def archive_bytes(
    *,
    name: str = "example-plugin",
    version: str = "1.0.0",
    payloads: dict[str, bytes] | None = None,
    extra_entries: list[tuple[zipfile.ZipInfo | str, bytes]] | None = None,
    compression: int = zipfile.ZIP_DEFLATED,
    declarations: list[dict] | None = None,
) -> bytes:
    payloads = payloads or {"skills/example/SKILL.md": b"# Example\n"}
    if declarations is None:
        declarations = [
            {
                "path": path,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            for path, content in payloads.items()
        ]
    manifest = {
        "schema_version": "1",
        "name": name,
        "version": version,
        "description": "Test plugin",
        "files": declarations,
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=compression) as package:
        package.writestr("plugin.json", json.dumps(manifest, separators=(",", ":")))
        for path, content in payloads.items():
            package.writestr(path, content)
        for entry, content in extra_entries or []:
            package.writestr(entry, content)
    return output.getvalue()


def write_archive(tmp_path: Path, content: bytes, name: str = "plugin.zip") -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


def sign(tmp_path: Path, content: bytes, private_key: Path) -> bytes:
    payload = tmp_path / "payload-to-sign"
    signature = tmp_path / "payload.sig"
    payload.write_bytes(content)
    subprocess.run(
        (
            "/usr/bin/openssl",
            "pkeyutl",
            "-sign",
            "-inkey",
            str(private_key),
            "-rawin",
            "-in",
            str(payload),
            "-out",
            str(signature),
        ),
        check=True,
        capture_output=True,
    )
    return signature.read_bytes()


def registry(tmp_path: Path, verifier) -> tuple[PluginRegistry, JsonlAuditLog]:
    audit = JsonlAuditLog(tmp_path / "audit.jsonl", fsync=False)
    return PluginRegistry(tmp_path / "registry", PluginArchiveReader(verifier), audit), audit


def test_signed_install_is_atomic_and_disabled_by_default(tmp_path: Path, signing_keys) -> None:
    private, public = signing_keys
    content = archive_bytes()
    signature = sign(tmp_path, content, private)
    plugin_registry, audit = registry(
        tmp_path,
        OpenSSLEd25519Verifier({"release": public}),
    )
    installed = plugin_registry.install(
        write_archive(tmp_path, content),
        signature=signature,
        key_id="release",
        audit_context=AUDIT_CONTEXT,
    )
    assert installed.enabled is False
    assert installed.install_path == (
        tmp_path / "registry/plugins/example-plugin/versions/1.0.0"
    )
    assert (installed.install_path / "skills/example/SKILL.md").read_bytes() == b"# Example\n"
    assert (installed.install_path / "skills/example/SKILL.md").stat().st_mode & 0o111 == 0
    assert not list(installed.install_path.parent.glob(".staging-*"))
    assert plugin_registry.list() == (installed,)
    assert [entry.event.event_type for entry in audit.verify()] == ["agent.plugin.installed"]


def test_signature_is_over_exact_archive_and_key_must_be_trusted(
    tmp_path: Path,
    signing_keys,
) -> None:
    private, public = signing_keys
    content = archive_bytes()
    signature = sign(tmp_path, content, private)
    path = write_archive(tmp_path, content)
    reader = PluginArchiveReader(OpenSSLEd25519Verifier({"release": public}))
    reader.read(path, signature=signature, key_id="release")
    path.write_bytes(content + b"x")
    with pytest.raises(PluginPackageError, match="signature"):
        reader.read(path, signature=signature, key_id="release")
    with pytest.raises(PluginPackageError, match="not trusted"):
        reader.read(
            write_archive(tmp_path, content, "fresh.zip"),
            signature=signature,
            key_id="unknown",
        )


@pytest.mark.parametrize(
    "bad_name",
    (
        "../escape",
        "/absolute",
        "a\\b",
        ".hidden",
        "a//b",
    ),
)
def test_archive_rejects_nonportable_and_traversal_paths(
    tmp_path: Path,
    bad_name: str,
) -> None:
    content = archive_bytes(extra_entries=[(bad_name, b"bad")])
    reader = PluginArchiveReader(AcceptVerifier())
    with pytest.raises(PluginPackageError, match="invalid path"):
        reader.read(
            write_archive(tmp_path, content),
            signature=b"test",
            key_id="test",
        )


@pytest.mark.parametrize("kind", (stat.S_IFLNK, stat.S_IFCHR, stat.S_IFIFO))
def test_archive_rejects_links_devices_and_fifos(tmp_path: Path, kind: int) -> None:
    entry = zipfile.ZipInfo("danger")
    entry.create_system = 3
    entry.external_attr = (kind | 0o600) << 16
    content = archive_bytes(extra_entries=[(entry, b"target")])
    with pytest.raises(PluginPackageError, match="links and devices"):
        PluginArchiveReader(AcceptVerifier()).read(
            write_archive(tmp_path, content),
            signature=b"test",
            key_id="test",
        )


@pytest.mark.filterwarnings("ignore:Duplicate name:UserWarning")
def test_archive_rejects_duplicate_and_case_colliding_paths(tmp_path: Path) -> None:
    for duplicate in ("skills/example/SKILL.md", "SKILLS/example/skill.md"):
        content = archive_bytes(extra_entries=[(duplicate, b"duplicate")])
        with pytest.raises(PluginPackageError, match="duplicate"):
            PluginArchiveReader(AcceptVerifier()).read(
                write_archive(tmp_path, content, f"{len(duplicate)}.zip"),
                signature=b"test",
                key_id="test",
            )


def test_archive_rejects_undeclared_hash_size_and_manifest_duplicates(tmp_path: Path) -> None:
    cases = (
        archive_bytes(extra_entries=[("extra.txt", b"extra")]),
        archive_bytes(
            declarations=[
                {
                    "path": "skills/example/SKILL.md",
                    "size": 10,
                    "sha256": "0" * 64,
                }
            ]
        ),
        archive_bytes(
            declarations=[
                {
                    "path": "skills/example/SKILL.md",
                    "size": 10,
                    "sha256": hashlib.sha256(b"# Example\n").hexdigest(),
                },
                {
                    "path": "SKILLS/example/skill.md",
                    "size": 10,
                    "sha256": hashlib.sha256(b"# Example\n").hexdigest(),
                },
            ]
        ),
    )
    reader = PluginArchiveReader(AcceptVerifier())
    for index, content in enumerate(cases):
        with pytest.raises(PluginPackageError):
            reader.read(
                write_archive(tmp_path, content, f"case-{index}.zip"),
                signature=b"test",
                key_id="test",
            )


def test_archive_rejects_expansion_bombs_and_excessive_entries(tmp_path: Path) -> None:
    bomb = archive_bytes(payloads={"bomb.bin": b"\x00" * 65_536})
    with pytest.raises(PluginPackageError, match="expansion ratio"):
        PluginArchiveReader(
            AcceptVerifier(),
            max_archive_bytes=1_048_576,
            max_expanded_bytes=1_048_576,
            max_file_bytes=1_048_576,
            max_expansion_ratio=10,
        ).read(write_archive(tmp_path, bomb), signature=b"test", key_id="test")

    many = archive_bytes(
        payloads={"a": b"a"},
        extra_entries=[("b", b"b"), ("c", b"c")],
    )
    with pytest.raises(PluginPackageError, match="entry count"):
        PluginArchiveReader(AcceptVerifier(), max_entries=2).read(
            write_archive(tmp_path, many, "many.zip"),
            signature=b"test",
            key_id="test",
        )


def test_archive_path_must_not_be_a_symlink(tmp_path: Path) -> None:
    target = write_archive(tmp_path, archive_bytes())
    link = tmp_path / "link.zip"
    link.symlink_to(target)
    with pytest.raises(PluginPackageError, match="open"):
        PluginArchiveReader(AcceptVerifier()).read(
            link,
            signature=b"test",
            key_id="test",
        )


def test_only_one_version_can_be_enabled_and_removal_is_recoverable(
    tmp_path: Path,
) -> None:
    plugin_registry, audit = registry(tmp_path, AcceptVerifier())
    for version in ("1.0.0", "2.0.0"):
        plugin_registry.install(
            write_archive(tmp_path, archive_bytes(version=version), f"{version}.zip"),
            signature=b"test",
            key_id="test",
            audit_context=AUDIT_CONTEXT,
        )
    first = plugin_registry.set_enabled(
        "example-plugin",
        "1.0.0",
        True,
        audit_context=AUDIT_CONTEXT,
    )
    assert first.enabled
    second = plugin_registry.set_enabled(
        "example-plugin",
        "2.0.0",
        True,
        audit_context=AUDIT_CONTEXT,
    )
    assert second.enabled
    assert [(item.version, item.enabled) for item in plugin_registry.list()] == [
        ("1.0.0", False),
        ("2.0.0", True),
    ]
    with pytest.raises(PluginRegistryError, match="disable"):
        plugin_registry.remove(
            "example-plugin",
            "2.0.0",
            audit_context=AUDIT_CONTEXT,
        )
    plugin_registry.set_enabled(
        "example-plugin",
        "2.0.0",
        False,
        audit_context=AUDIT_CONTEXT,
    )
    removed = plugin_registry.remove(
        "example-plugin",
        "2.0.0",
        audit_context=AUDIT_CONTEXT,
    )
    assert removed.trash_path.is_dir()
    restored = plugin_registry.restore(
        removed.removal_id,
        audit_context=AUDIT_CONTEXT,
    )
    assert restored.enabled is False
    assert restored.install_path.is_dir()
    event_types = [entry.event.event_type for entry in audit.verify()]
    assert "agent.plugin.removed" in event_types
    assert "agent.plugin.restored" in event_types


def test_registry_rejects_insecure_or_linked_state_paths(tmp_path: Path) -> None:
    insecure = tmp_path / "insecure"
    insecure.mkdir(mode=0o755)
    with pytest.raises(PluginRegistryError, match="private"):
        PluginRegistry(
            insecure,
            PluginArchiveReader(AcceptVerifier()),
            JsonlAuditLog(tmp_path / "audit.jsonl", fsync=False),
        )

    target = tmp_path / "real"
    target.mkdir(mode=0o700)
    linked = tmp_path / "linked"
    linked.symlink_to(target, target_is_directory=True)
    with pytest.raises(PluginRegistryError, match="private"):
        PluginRegistry(
            linked,
            PluginArchiveReader(AcceptVerifier()),
            JsonlAuditLog(tmp_path / "other-audit.jsonl", fsync=False),
        )


def test_enable_revalidates_installed_content(tmp_path: Path) -> None:
    plugin_registry, _ = registry(tmp_path, AcceptVerifier())
    installed = plugin_registry.install(
        write_archive(tmp_path, archive_bytes()),
        signature=b"test",
        key_id="test",
        audit_context=AUDIT_CONTEXT,
    )
    (installed.install_path / "skills/example/SKILL.md").write_bytes(b"tampered")
    with pytest.raises(PluginRegistryError, match="integrity"):
        plugin_registry.set_enabled(
            "example-plugin",
            "1.0.0",
            True,
            audit_context=AUDIT_CONTEXT,
        )
    assert plugin_registry.list()[0].enabled is False


def test_failed_staging_and_audit_leave_no_published_plugin(
    tmp_path: Path,
    monkeypatch,
) -> None:
    audit_log = JsonlAuditLog(tmp_path / "audit.jsonl", fsync=False)
    audit = ToggleAudit(audit_log)
    plugin_registry = PluginRegistry(
        tmp_path / "registry",
        PluginArchiveReader(AcceptVerifier()),
        audit,
    )
    archive = write_archive(tmp_path, archive_bytes())
    original_write = plugin_module._write_package

    def fail_write(staging: Path, files: dict[str, bytes]) -> None:
        original_write(staging, {"plugin.json": files["plugin.json"]})
        raise OSError("simulated write failure")

    monkeypatch.setattr(plugin_module, "_write_package", fail_write)
    with pytest.raises(OSError, match="simulated"):
        plugin_registry.install(
            archive,
            signature=b"test",
            key_id="test",
            audit_context=AUDIT_CONTEXT,
        )
    assert plugin_registry.list() == ()
    versions = tmp_path / "registry/plugins/example-plugin/versions"
    assert not list(versions.glob(".staging-*"))

    monkeypatch.setattr(plugin_module, "_write_package", original_write)
    audit.fail = True
    with pytest.raises(RuntimeError, match="audit"):
        plugin_registry.install(
            archive,
            signature=b"test",
            key_id="test",
            audit_context=AUDIT_CONTEXT,
        )
    assert plugin_registry.list() == ()
    assert not (versions / "1.0.0").exists()


def test_audit_failure_rolls_back_state_change_and_removal(tmp_path: Path) -> None:
    audit_log = JsonlAuditLog(tmp_path / "audit.jsonl", fsync=False)
    audit = ToggleAudit(audit_log)
    plugin_registry = PluginRegistry(
        tmp_path / "registry",
        PluginArchiveReader(AcceptVerifier()),
        audit,
    )
    installed = plugin_registry.install(
        write_archive(tmp_path, archive_bytes()),
        signature=b"test",
        key_id="test",
        audit_context=AUDIT_CONTEXT,
    )
    second = plugin_registry.install(
        write_archive(tmp_path, archive_bytes(version="2.0.0"), "second.zip"),
        signature=b"test",
        key_id="test",
        audit_context=AUDIT_CONTEXT,
    )
    plugin_registry.set_enabled(
        installed.name,
        installed.version,
        True,
        audit_context=AUDIT_CONTEXT,
    )
    audit.fail = True
    with pytest.raises(RuntimeError, match="audit"):
        plugin_registry.set_enabled(
            second.name,
            second.version,
            True,
            audit_context=AUDIT_CONTEXT,
        )
    assert [(item.version, item.enabled) for item in plugin_registry.list()] == [
        ("1.0.0", True),
        ("2.0.0", False),
    ]
    with pytest.raises(RuntimeError, match="audit"):
        plugin_registry.remove(
            second.name,
            second.version,
            audit_context=AUDIT_CONTEXT,
        )
    assert all(item.install_path.is_dir() for item in plugin_registry.list())
    assert not any((tmp_path / "registry/.trash").iterdir())


def test_gateway_build_excludes_agent_plugins_and_execution_code() -> None:
    repository = Path(__file__).resolve().parents[1]
    dockerfile = (repository / "Dockerfile").read_text()
    gateway_sources = "\n".join(
        path.read_text()
        for path in sorted((repository / "src/zeaz_provider").glob("*.py"))
    )
    assert "COPY packages" not in dockerfile
    assert "zeaz_agent" not in gateway_sources
    assert "PluginRegistry" not in gateway_sources
    assert "create_subprocess" not in gateway_sources
