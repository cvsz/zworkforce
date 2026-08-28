from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def maintenance_environment(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    prefix = tmp_path / "install"
    bin_dir = tmp_path / "bin"
    service_dir = tmp_path / "config-home" / "systemd" / "user"
    version_dir = prefix / "versions" / "0.4.0rc1"
    version_dir.mkdir(parents=True)
    (version_dir / "bin").mkdir()
    executable(
        version_dir / "bin" / "python",
        """#!/usr/bin/env bash
set -Eeuo pipefail
if [[ "${1:-}" == "-c" ]]; then
  printf '%s\n' "0.4.0rc1"
fi
""",
    )
    (prefix / "backups").mkdir(parents=True)
    (prefix / "config").mkdir()
    (prefix / "current").symlink_to(version_dir)
    bin_dir.mkdir()
    executable(
        bin_dir / "systemctl",
        """#!/usr/bin/env bash
set -Eeuo pipefail
exit 0
""",
    )
    executable(bin_dir / "zeaz-provider", "#!/usr/bin/env bash\nexit 0\n")
    service_dir.mkdir(parents=True)
    (service_dir / "zeaz-provider.service").write_text("service", encoding="utf-8")
    (service_dir / "zeaz-provider-update.service").write_text("service", encoding="utf-8")
    (service_dir / "zeaz-provider-update.timer").write_text("timer", encoding="utf-8")
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "XDG_CONFIG_HOME": str(tmp_path / "config-home"),
            "ZEAZ_INSTALL_PREFIX": str(prefix),
            "ZEAZ_BIN_DIR": str(bin_dir),
        }
    )
    return env, prefix, bin_dir


def run(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_uninstall_dry_run_is_non_mutating(tmp_path: Path) -> None:
    env, prefix, bin_dir = maintenance_environment(tmp_path)

    result = run("bash", "scripts/uninstall.sh", "--dry-run", "--prefix", str(prefix), env=env)

    assert result.returncode == 0, result.stderr
    assert "current" in result.stdout
    assert (bin_dir / "zeaz-provider").exists()
    assert (prefix / "current").exists()
    assert (tmp_path / "config-home" / "systemd" / "user" / "zeaz-provider.service").exists()


def test_uninstall_apply_removes_wrapper_and_units(tmp_path: Path) -> None:
    env, prefix, bin_dir = maintenance_environment(tmp_path)

    result = run("bash", "scripts/uninstall.sh", "--apply", "--prefix", str(prefix), env=env)

    assert result.returncode == 0, result.stderr
    assert not (bin_dir / "zeaz-provider").exists()
    assert not (prefix / "current").exists()
    assert not (tmp_path / "config-home" / "systemd" / "user" / "zeaz-provider.service").exists()
    assert (prefix / "backups" / "last-uninstall").exists()
    assert (prefix / "versions" / "0.4.0rc1").exists()
    assert (prefix / "config").exists()


def test_doctor_reports_healthy_install_as_json(tmp_path: Path) -> None:
    env, prefix, bin_dir = maintenance_environment(tmp_path)

    result = run("bash", "scripts/doctor.sh", "--json", env=env)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {
        "current": True,
        "service_file": True,
        "status": "healthy",
        "update_service": True,
        "update_timer": True,
        "version": "0.4.0rc1",
        "wrapper": True,
    }
