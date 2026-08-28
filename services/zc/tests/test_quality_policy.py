"""Regression checks for scoped lint and security policy."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"


def _config() -> dict:
    with PYPROJECT.open("rb") as config_file:
        return tomllib.load(config_file)


def test_ruff_has_no_repository_wide_ignores() -> None:
    lint = _config()["tool"]["ruff"]["lint"]

    assert not lint.get("ignore")
    assert lint["per-file-ignores"]


def test_supported_api_does_not_inherit_legacy_correctness_waivers() -> None:
    per_file = _config()["tool"]["ruff"]["lint"]["per-file-ignores"]
    app_waivers = set(per_file["app/**/*.py"])

    assert app_waivers == {"E501"}
    assert {"E701", "E702", "F401", "F841", "B007"} <= set(
        per_file["src/wire/**/*.py"]
    )


def test_bandit_has_no_global_test_skips() -> None:
    bandit = _config()["tool"]["bandit"]

    assert not bandit.get("skips")
