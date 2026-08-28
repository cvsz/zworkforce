"""CLI compatibility commands must use explicit resource API paths."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from wire.api_client import EnterpriseAPIError
from wire.enterprise_commands import dispatch_enterprise_resource_command


class Args(SimpleNamespace):
    """Argparse-like namespace returning None for unrelated flags."""

    def __getattr__(self, _name):
        return None


class FakeClient:
    def __init__(self) -> None:
        self.calls = []

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        return {"data": {"id": "prj_test", "name": "Migration"}}


def test_project_create_maps_to_explicit_resource_endpoint(monkeypatch) -> None:
    client = FakeClient()
    monkeypatch.setattr(
        "wire.enterprise_commands.EnterpriseAPIClient.from_env",
        lambda: client,
    )
    args = Args(
        project_create="Migration",
        project_desc="Move CLI domain",
        project_template="blank",
    )

    handled = dispatch_enterprise_resource_command(args)

    assert handled is True
    assert client.calls == [
        (
            "POST",
            "/v1/projects",
            {
                "name": "Migration",
                "description": "Move CLI domain",
                "template": "blank",
            },
        )
    ]


def test_migrated_command_never_falls_back_without_api(monkeypatch) -> None:
    monkeypatch.setattr(
        "wire.enterprise_commands.EnterpriseAPIClient.from_env",
        lambda: None,
    )

    with pytest.raises(EnterpriseAPIError, match="migrated"):
        dispatch_enterprise_resource_command(Args(file_list=True))


def test_unrelated_command_is_not_claimed(monkeypatch) -> None:
    monkeypatch.setattr(
        "wire.enterprise_commands.EnterpriseAPIClient.from_env",
        lambda: pytest.fail("API client should not be constructed"),
    )

    assert dispatch_enterprise_resource_command(Args(tui=True)) is False


def test_no_generic_command_execution_route_exists() -> None:
    from app.main import app

    paths = {
        route.path
        for route in app.routes
        if hasattr(route, "path")
    }
    forbidden = {
        "/v1/commands",
        "/v1/execute",
        "/v1/cli",
        "/v1/shell",
    }

    assert paths.isdisjoint(forbidden)
