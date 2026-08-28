"""Regression checks for reproducible deployment dependencies."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME_PATTERN = re.compile(r"^([A-Za-z0-9_.-]+)")


def _requirement_blocks(path: Path) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        current.append(line.removesuffix("\\").strip())
        if not line.endswith("\\"):
            blocks.append(" ".join(current))
            current = []

    assert not current, f"unterminated requirement in {path}"
    return blocks


def _normalized_name(requirement: str) -> str:
    match = NAME_PATTERN.match(requirement)
    assert match, f"invalid requirement: {requirement}"
    return match.group(1).lower().replace("_", "-").replace(".", "-")


def test_deployment_lock_pins_and_hashes_every_package() -> None:
    blocks = _requirement_blocks(ROOT / "requirements-deploy.lock")

    assert blocks
    for block in blocks:
        assert "==" in block, f"deployment dependency is not pinned: {block}"
        assert "--hash=sha256:" in block, f"deployment dependency has no hash: {block}"


def test_deployment_lock_contains_every_direct_runtime_dependency() -> None:
    direct = {
        _normalized_name(block)
        for block in _requirement_blocks(ROOT / "requirements-deploy.in")
    }
    locked = {
        _normalized_name(block)
        for block in _requirement_blocks(ROOT / "requirements-deploy.lock")
    }

    assert direct <= locked


def test_docker_build_requires_the_hashed_lock() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY requirements-deploy.lock ./" in dockerfile
    assert "--require-hashes -r requirements-deploy.lock" in dockerfile
    assert "requirements-enterprise.txt" not in dockerfile
