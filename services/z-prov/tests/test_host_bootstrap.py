from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def executable(path: Path, content: str = "#!/usr/bin/env bash\nexit 0\n") -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def bootstrap_environment(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    host_root = tmp_path / "host"
    (host_root / "sys/class/dmi/id").mkdir(parents=True)
    (host_root / "sys/class/dmi/id/sys_vendor").write_text("VMware, Inc.\n", encoding="utf-8")
    os_release = tmp_path / "os-release"
    os_release.write_text(
        'ID="ubuntu"\nVERSION_ID="26.04"\nVERSION_CODENAME="resolve"\n', encoding="utf-8"
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for command in ("apt-get", "curl", "ufw", "sysctl", "systemctl", "runuser", "loginctl", "dpkg"):
        executable(bin_dir / command)
    executable(
        bin_dir / "gpg",
        """#!/usr/bin/env bash
set -Eeuo pipefail
while [[ "$#" -gt 0 ]]; do
  if [[ "$1" == "--output" ]]; then
    touch "$2"
    exit 0
  fi
  shift
done
""",
    )
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "ZEAZ_BOOTSTRAP_TEST_ROOT": "1",
        }
    )
    return env, host_root, os_release


def run(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, env=env, check=False, capture_output=True, text=True)


def test_bootstrap_dry_run_is_cpu_only_and_non_mutating(tmp_path: Path) -> None:
    env, host_root, os_release = bootstrap_environment(tmp_path)
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))

    result = run(
        "bash", "scripts/bootstrap-host.sh", "--dry-run", "--mode", "cpu-only", "--root", str(host_root),
        "--os-release", str(os_release), env=env,
    )

    after = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    assert result.returncode == 0, result.stderr
    assert "mode=cpu-only" in result.stdout
    assert "NVIDIA" not in result.stdout
    assert before == after


def test_bootstrap_auto_detects_amd_from_card_vendor_file(tmp_path: Path) -> None:
    env, host_root, os_release = bootstrap_environment(tmp_path)
    vendor = host_root / "sys/class/drm/card0/device/vendor"
    vendor.parent.mkdir(parents=True)
    vendor.write_text("0x1002\n", encoding="utf-8")

    result = run(
        "bash",
        "scripts/bootstrap-host.sh",
        "--dry-run",
        "--root",
        str(host_root),
        "--os-release",
        str(os_release),
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "mode=amd" in result.stdout


def test_bootstrap_apply_writes_persistent_cpu_and_vmware_policy(tmp_path: Path) -> None:
    env, host_root, os_release = bootstrap_environment(tmp_path)

    result = run(
        "bash", "scripts/bootstrap-host.sh", "--apply", "--mode", "cpu-only", "--install-user", "root",
        "--root", str(host_root), "--os-release", str(os_release), env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "nvidia-container-toolkit" not in result.stdout
    docker_source = (host_root / "etc/apt/sources.list.d/docker.list").read_text(encoding="utf-8")
    sysctl_policy = (host_root / "etc/sysctl.d/99-zeaz-provider.conf").read_text(encoding="utf-8")
    assert docker_source.endswith("resolve stable\n")
    assert "vm.swappiness = 10" in sysctl_policy
    assert "65536" in (host_root / "etc/security/limits.d/99-zeaz-provider.conf").read_text(encoding="utf-8")
    assert '"live-restore":true' in (host_root / "etc/docker/daemon.json").read_text(encoding="utf-8")


def test_bootstrap_removes_distribution_docker_conflicts_before_install(tmp_path: Path) -> None:
    env, host_root, os_release = bootstrap_environment(tmp_path)
    command_log = tmp_path / "apt-commands"
    executable(
        tmp_path / "bin/apt-get",
        f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> {command_log}\n",
    )

    result = run(
        "bash",
        "scripts/bootstrap-host.sh",
        "--apply",
        "--mode",
        "cpu-only",
        "--install-user",
        "root",
        "--root",
        str(host_root),
        "--os-release",
        str(os_release),
        env=env,
    )

    assert result.returncode == 0, result.stderr
    commands = command_log.read_text(encoding="utf-8").splitlines()
    removal = "remove -y docker.io docker-compose docker-compose-v2 docker-doc podman-docker containerd runc"
    official_install = "install -y --no-install-recommends docker-ce docker-ce-cli containerd.io"
    assert removal in commands
    assert "install -y --no-install-recommends ca-certificates curl gnupg python3-venv" in commands
    assert commands.index(removal) < next(
        index for index, command in enumerate(commands) if command.startswith(official_install)
    )


def test_bootstrap_starts_user_manager_before_user_service_install(tmp_path: Path) -> None:
    source = (ROOT / "scripts/bootstrap-host.sh").read_text(encoding="utf-8")

    assert source.index('loginctl enable-linger "$INSTALL_USER"') < source.index(
        'bash "$ROOT/scripts/install.sh" --apply --systemd-user'
    )
    assert 'DBUS_SESSION_BUS_ADDRESS="unix:path=$runtime_dir/bus"' in source
def test_bootstrap_nvidia_path_is_explicit(tmp_path: Path) -> None:
    env, host_root, os_release = bootstrap_environment(tmp_path)
    command_log = tmp_path / "commands"
    executable(
        tmp_path / "bin/apt-get",
        f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> {command_log}\n",
    )
    executable(tmp_path / "bin/nvidia-ctk")
    executable(tmp_path / "bin/nvidia-smi")

    result = run(
        "bash", "scripts/bootstrap-host.sh", "--apply", "--mode", "nvidia", "--install-user", "root",
        "--root", str(host_root), "--os-release", str(os_release), env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "nvidia-container-toolkit" in command_log.read_text(encoding="utf-8")
    assert (host_root / "etc/apt/sources.list.d/nvidia-container-toolkit.list").exists()


def test_bootstrap_rejects_partial_auto_update_configuration(tmp_path: Path) -> None:
    env, host_root, os_release = bootstrap_environment(tmp_path)

    result = run(
        "bash",
        "scripts/bootstrap-host.sh",
        "--dry-run",
        "--root",
        str(host_root),
        "--os-release",
        str(os_release),
        "--update-manifest-url",
        "https://releases.example/manifest.json",
        env=env,
    )

    assert result.returncode != 0
    assert "--update-public-key" in result.stdout
    assert "required" in result.stdout
