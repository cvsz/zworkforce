import re
from pathlib import Path

import yaml


def test_compose_enforces_container_security_boundaries():
    compose = yaml.safe_load(Path("compose.yaml").read_text(encoding="utf-8"))
    provider = compose["services"]["provider"]

    assert provider["read_only"] is True
    assert "ALL" in provider["cap_drop"]
    assert "no-new-privileges:true" in provider["security_opt"]
    assert all(volume.endswith(":ro") for volume in provider["volumes"])
    assert all(port.startswith("127.0.0.1:") for port in provider["ports"])
    assert any(
        mount.startswith("/tmp:") and "size=64m" in mount and "mode=1777" in mount
        for mount in provider["tmpfs"]
    )


def test_final_container_stage_runs_as_dedicated_non_root_user():
    lines = [
        line.strip()
        for line in Path("Dockerfile").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    final_stage = lines[max(index for index, line in enumerate(lines) if line.startswith("FROM ")) :]

    assert any("useradd --uid 10001" in line for line in final_stage)
    assert "USER zeaz" in final_stage
    assert not any(line == "USER root" for line in final_stage)


def test_every_container_stage_uses_a_sha256_pinned_base_image():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    images = re.findall(r"^FROM\s+(\S+)", dockerfile, flags=re.MULTILINE)
    assert images
    assert all(re.fullmatch(r"[^@]+@sha256:[0-9a-f]{64}", image) for image in images)


def test_docker_context_excludes_credentials_and_local_state():
    exclusions = {
        line.strip()
        for line in Path(".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert {
        ".env",
        ".git",
        ".venv",
        "config/providers.yaml",
        "dist",
    } <= exclusions
