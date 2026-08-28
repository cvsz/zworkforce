"""Enforce the product dependency and packaging boundaries from ADR-001."""

import ast
import configparser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _import_roots(source_root: Path) -> set[str]:
    roots: set[str] = set()
    for path in source_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.partition(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots.add(node.module.partition(".")[0])
    return roots


def test_supported_api_is_independent_from_compatibility_surfaces() -> None:
    assert _import_roots(ROOT / "app").isdisjoint({"wire", "webapp"})


def test_compatibility_cli_is_independent_from_server_and_web_adapter() -> None:
    assert _import_roots(ROOT / "src" / "wire").isdisjoint({"app", "webapp"})


def test_runtime_package_manifest_excludes_agent_tooling() -> None:
    config = configparser.ConfigParser()
    config.read(ROOT / "setup.cfg")
    packages = set(config["options"]["packages"].split())

    assert {"app", "wire", "webapp"} <= packages
    assert not any(
        package == "agents"
        or package.startswith("agents.")
        or package == "zc"
        or package.startswith("zc.")
        for package in packages
    )


def test_console_commands_expose_cli_and_api_boundaries() -> None:
    config = configparser.ConfigParser()
    config.read(ROOT / "setup.cfg")
    entry_points = config["options.entry_points"]["console_scripts"]

    assert "zc = app.main:cli" in entry_points
    assert "zcoder = app.main:cli" in entry_points
    assert "zc-api = app.main:run_server" in entry_points
    assert "zc-legacy = wire.main:main" in entry_points
