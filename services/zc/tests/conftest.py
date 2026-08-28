"""tests/conftest.py — shared fixtures"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

for path in (SRC, ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

import pytest


def pytest_configure(config):
    """Keep the suite isolated from optional globally-installed plugins.

    LangSmith's pytest plugin can wrap the in-process ASGI test transport and
    deadlock synchronous tests in environments where it is installed outside
    this project. It is not a project dependency or part of the test contract.
    """
    plugin_manager = config.pluginmanager
    for plugin_name in ("langsmith.pytest_plugin", "langsmith"):
        plugin = plugin_manager.get_plugin(plugin_name)
        if plugin is not None:
            plugin_manager.unregister(plugin)


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Every test gets its own config file path so tests never read/write
    a real ~/.ai-coder-config.json on the machine running the suite."""
    fake_config = tmp_path / ".ai-coder-config.json"
    monkeypatch.setattr("wire.config.CONFIG_PATH", str(fake_config))
    yield fake_config


@pytest.fixture(autouse=True)
def no_real_api_key(monkeypatch):
    """Prevent tests from accidentally hitting the real API because a
    developer happens to have ANTHROPIC_API_KEY set in their shell."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    yield


@pytest.fixture
def fake_logger_setup():
    from wire.logging_config import setup_logging
    setup_logging(level="DEBUG", fmt="text")
