"""Local no-cost runtime profile tests."""

from __future__ import annotations

from app.local import LOCAL_DEFAULTS, apply_local_defaults


def test_local_defaults_disable_external_paid_dependencies(monkeypatch) -> None:
    for key in LOCAL_DEFAULTS:
        monkeypatch.delenv(key, raising=False)

    apply_local_defaults()

    assert LOCAL_DEFAULTS["STORAGE_BACKEND"] == "local"
    assert LOCAL_DEFAULTS["REDIS_ENABLED"] == "false"
    assert LOCAL_DEFAULTS["NATS_ENABLED"] == "false"
    assert LOCAL_DEFAULTS["AUTH_REQUIRED"] == "false"


def test_local_defaults_do_not_override_explicit_environment(monkeypatch) -> None:
    monkeypatch.setenv("API_PORT", "9123")
    apply_local_defaults()
    assert __import__("os").environ["API_PORT"] == "9123"
