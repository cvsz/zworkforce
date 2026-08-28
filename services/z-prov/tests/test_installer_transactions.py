from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = "0.4.0rc1"


def executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def installer_environment(tmp_path: Path, pip_mode: str = "success") -> tuple[dict[str, str], Path]:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    executable(
        fake_bin / "python3",
        """#!/usr/bin/env bash
set -Eeuo pipefail
if [[ "${1:-}" == "-m" && "${2:-}" == "venv" ]]; then
  target="$3"
  mkdir -p "$target/bin"
  cat >"$target/bin/pip" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
case "${FAKE_PIP_MODE:-success}" in
  success) exit 0 ;;
  fail) exit 42 ;;
  interrupt) kill -TERM "$PPID"; sleep 1; exit 143 ;;
esac
EOF
  cat >"$target/bin/python" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
  cat >"$target/bin/zeaz-provider" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
  chmod +x "$target/bin/pip" "$target/bin/python" "$target/bin/zeaz-provider"
fi
exit 0
""",
    )
    prefix = tmp_path / "install"
    bin_dir = tmp_path / "bin"
    old = prefix / "versions" / "0.3.0"
    old.mkdir(parents=True)
    (prefix / "backups").mkdir()
    (prefix / "current").symlink_to(old)
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "FAKE_PIP_MODE": pip_mode,
            "ZEAZ_BIN_DIR": str(bin_dir),
            "XDG_CONFIG_HOME": str(tmp_path / "config-home"),
        }
    )
    return env, prefix


def install(prefix: Path, env: dict[str, str], *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("bash", "scripts/install.sh", "--apply", "--prefix", str(prefix), *extra),
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_successful_install_atomically_switches_current(tmp_path: Path) -> None:
    env, prefix = installer_environment(tmp_path)

    result = install(prefix, env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (prefix / "current").resolve() == prefix / "versions" / VERSION
    assert not list((prefix / "versions").glob(".*.staging.*"))
    backup = (prefix / "backups" / "last-install").read_text(encoding="utf-8")
    assert f"installed={VERSION}" in backup
    assert "previous=" in backup


def test_post_switch_failure_automatically_rolls_back(tmp_path: Path) -> None:
    env, prefix = installer_environment(tmp_path)
    fake_systemctl = Path(env["PATH"].split(":", 1)[0]) / "systemctl"
    executable(
        fake_systemctl,
        """#!/usr/bin/env bash
[[ "${2:-}" == "daemon-reload" ]] && exit 0
exit 42
""",
    )

    result = install(prefix, env, "--systemd-user")

    assert result.returncode != 0
    assert (prefix / "current").resolve() == prefix / "versions" / "0.3.0"
    assert "restored previous installation" in result.stdout.replace("\\ ", " ")
    assert not (prefix / "backups" / "last-install").exists()


def test_interrupted_staging_is_removed_without_switching(tmp_path: Path) -> None:
    env, prefix = installer_environment(tmp_path, pip_mode="interrupt")

    result = install(prefix, env)

    assert result.returncode != 0
    assert (prefix / "current").resolve() == prefix / "versions" / "0.3.0"
    assert not (prefix / "versions" / VERSION).exists()
    assert not list((prefix / "versions").glob(".*.staging.*"))
    assert not (prefix / "backups" / "last-install").exists()
