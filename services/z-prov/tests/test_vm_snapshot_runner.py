from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_vm_snapshot_runner_dry_run_never_connects(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    ssh = bin_dir / "ssh"
    ssh.write_text("#!/usr/bin/env bash\nexit 99\n", encoding="utf-8")
    ssh.chmod(0o755)

    result = subprocess.run(
        [
            "bash",
            "scripts/test-vm-snapshot.sh",
            "--dry-run",
            "--host",
            "ubuntu@vmware.test",
            "--install-user",
            "zeaz",
        ],
        cwd=ROOT,
        env={"PATH": f"{bin_dir}:{__import__('os').environ['PATH']}"},
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Ubuntu\\ 26.04\\ VMware" in result.stdout


def test_vm_snapshot_runner_apply_requires_signed_upgrade_inputs() -> None:
    result = subprocess.run(
        [
            "bash",
            "scripts/test-vm-snapshot.sh",
            "--apply",
            "--host",
            "ubuntu@vmware.test",
            "--install-user",
            "zeaz",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "signed\\ update\\ manifest" in result.stdout


def test_vm_snapshot_runner_rejects_relative_identity_file() -> None:
    result = subprocess.run(
        [
            "bash",
            "scripts/test-vm-snapshot.sh",
            "--dry-run",
            "--host",
            "ubuntu@vmware.test",
            "--install-user",
            "zeaz",
            "--identity-file",
            "id_ed25519",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "--identity-file" in result.stdout


def test_vm_snapshot_runner_accepts_interactive_sudo_mode_in_dry_run() -> None:
    result = subprocess.run(
        [
            "bash",
            "scripts/test-vm-snapshot.sh",
            "--dry-run",
            "--host",
            "ubuntu@vmware.test",
            "--install-user",
            "zeaz",
            "--sudo-mode",
            "interactive",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_interactive_sudo_tty_is_not_used_for_archive_transfer() -> None:
    source = (ROOT / "scripts/test-vm-snapshot.sh").read_text(encoding="utf-8")

    assert 'sudo_ssh_options+=(-tt)' in source
    assert 'remote() { ssh "${ssh_options[@]}"' in source
    assert 'remote_sudo_transport() { ssh "${sudo_ssh_options[@]}"' in source
    assert 'remote "tar -C \'$remote_dir\' -xf -"' in source


def test_remote_sudo_decodes_command_payload_before_running_bash() -> None:
    source = (ROOT / "scripts/test-vm-snapshot.sh").read_text(encoding="utf-8")

    assert "| base64 -d | sudo -u '$user' /bin/bash" in source
    assert "| base64 -d | sudo -n -u '$user' /bin/bash" in source


def test_vm_snapshot_runner_keep_workdir_is_dry_run_safe() -> None:
    result = subprocess.run(
        [
            "bash",
            "scripts/test-vm-snapshot.sh",
            "--dry-run",
            "--host",
            "ubuntu@vmware.test",
            "--install-user",
            "zeaz",
            "--keep-remote-workdir",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "retain\\ the\\ secret-excluded" in result.stdout


def test_vm_snapshot_runner_requires_noninteractive_sudo_before_transfer() -> None:
    source = (ROOT / "scripts/test-vm-snapshot.sh").read_text(encoding="utf-8")

    assert "remote 'sudo -n true'" in source
    assert source.index("remote 'sudo -n true'") < source.index('tar -C "$ROOT"')
