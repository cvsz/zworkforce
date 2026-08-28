from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def update_environment(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    private_key = tmp_path / "private.pem"
    public_key = tmp_path / "public.pem"
    generated = run("openssl", "genpkey", "-algorithm", "ED25519", "-out", str(private_key))
    assert generated.returncode == 0, generated.stderr
    exported = run(
        "openssl",
        "pkey",
        "-in",
        str(private_key),
        "-pubout",
        "-out",
        str(public_key),
    )
    assert exported.returncode == 0, exported.stderr

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": "9.9.9",
                "url": "https://updates.example/release.zip",
                "sha256": "a" * 64,
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    signature = tmp_path / "manifest.sig"
    signed = run(
        "bash",
        "scripts/sign-update-manifest.sh",
        str(manifest),
        str(private_key),
        str(signature),
    )
    assert signed.returncode == 0, signed.stderr

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        """#!/usr/bin/env bash
set -Eeuo pipefail
out=""
url=""
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    -o) shift; out="$1" ;;
    https://updates.example/latest.json) url=manifest ;;
    https://updates.example/latest.json.sig) url=signature ;;
  esac
  shift
done
[[ -n "$out" && -n "$url" ]]
if [[ "$url" == manifest ]]; then
  cp -- "$TEST_MANIFEST" "$out"
else
  cp -- "$TEST_SIGNATURE" "$out"
fi
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "TEST_MANIFEST": str(manifest),
            "TEST_SIGNATURE": str(signature),
            "ZEAZ_UPDATE_MANIFEST_URL": "https://updates.example/latest.json",
            "ZEAZ_UPDATE_PUBLIC_KEY": str(public_key),
            "ZEAZ_INSTALL_PREFIX": str(tmp_path / "install"),
        }
    )
    return env, manifest, signature


def test_valid_signed_manifest_is_accepted(tmp_path: Path) -> None:
    env, _, _ = update_environment(tmp_path)

    result = run("bash", "scripts/update.sh", "--check", env=env)

    assert result.returncode == 0, result.stderr
    assert "target=9.9.9" in result.stdout
    assert not (tmp_path / "install").exists()


def test_tampered_manifest_fails_before_installation(tmp_path: Path) -> None:
    env, manifest, _ = update_environment(tmp_path)
    manifest.write_text(manifest.read_text(encoding="utf-8").replace("9.9.9", "9.9.8"), encoding="utf-8")

    result = run("bash", "scripts/update.sh", "--apply", env={**env, "CONFIRM_UPDATE": "yes"})

    assert result.returncode != 0
    assert "signature verification failed" in result.stdout.replace("\\ ", " ")
    assert not (tmp_path / "install").exists()


def test_signature_from_untrusted_key_is_rejected(tmp_path: Path) -> None:
    env, manifest, signature = update_environment(tmp_path)
    other_key = tmp_path / "other.pem"
    assert run("openssl", "genpkey", "-algorithm", "ED25519", "-out", str(other_key)).returncode == 0
    assert (
        run(
            "bash",
            "scripts/sign-update-manifest.sh",
            str(manifest),
            str(other_key),
            str(signature),
        ).returncode
        == 0
    )

    result = run("bash", "scripts/update.sh", "--check", env=env)

    assert result.returncode != 0
    assert "signature verification failed" in result.stdout.replace("\\ ", " ")


def test_update_requires_explicit_public_key(tmp_path: Path) -> None:
    env, _, _ = update_environment(tmp_path)
    env.pop("ZEAZ_UPDATE_PUBLIC_KEY")

    result = run("bash", "scripts/update.sh", "--check", env=env)

    assert result.returncode != 0
    assert "ZEAZ_UPDATE_PUBLIC_KEY" in result.stdout
