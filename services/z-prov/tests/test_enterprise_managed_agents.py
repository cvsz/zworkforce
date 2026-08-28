import json

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from zeaz_enterprise.managed_agents import (
    MANAGED_AGENTS_BETA,
    AnthropicManagedAgentsAdapter,
    CloudEnvironmentConfig,
    CronSchedule,
    DeploymentSpec,
    EnvironmentSpec,
    LimitedNetwork,
    ManagedAgentAdapterError,
    ManagedAgentCredential,
    TextBlock,
    UserMessage,
)

API_KEY = "regular-managed-agent-test-key"


def credential() -> ManagedAgentCredential:
    return ManagedAgentCredential(secret=SecretStr(API_KEY))


def environment(environment_id: str = "env_1", *, archived: bool = False) -> dict:
    return {
        "id": environment_id,
        "type": "environment",
        "name": "Production",
        "description": "Restricted production sandbox",
        "config": {
            "type": "cloud",
            "networking": {
                "type": "limited",
                "allowed_hosts": ["api.example.com"],
                "allow_mcp_servers": False,
                "allow_package_managers": False,
            },
            "packages": {"type": "packages", "pip": ["httpx"]},
        },
        "metadata": {"env": "prod"},
        "scope": None,
        "created_at": "2026-07-01T00:00:00Z",
        "updated_at": "2026-07-02T00:00:00Z",
        "archived_at": "2026-07-03T00:00:00Z" if archived else None,
    }


def deployment(deployment_id: str = "depl_1", *, status: str = "active") -> dict:
    return {
        "id": deployment_id,
        "type": "deployment",
        "name": "Weekly scan",
        "description": "ignored normalized field",
        "status": status,
        "agent": {"type": "agent", "id": "agent_1", "version": 3},
        "environment_id": "env_1",
        "initial_events": [],
        "schedule": {
            "type": "cron",
            "expression": "0 20 * * 5",
            "timezone": "UTC",
            "last_run_at": None,
            "upcoming_runs_at": [],
        },
        "metadata": {},
        "vault_ids": [],
        "resources": [],
        "paused_reason": None,
        "created_at": "2026-07-01T00:00:00Z",
        "updated_at": "2026-07-02T00:00:00Z",
        "archived_at": None,
    }


def adapter(handler, **changes) -> AnthropicManagedAgentsAdapter:
    values = {
        "credential": credential(),
        "client": httpx.AsyncClient(
            transport=httpx.MockTransport(handler), trust_env=False
        ),
    }
    values.update(changes)
    return AnthropicManagedAgentsAdapter(**values)


def environment_spec() -> EnvironmentSpec:
    return EnvironmentSpec(
        name="Production",
        description="Restricted production sandbox",
        config=CloudEnvironmentConfig(
            networking=LimitedNetwork(allowed_hosts=("api.example.com",))
        ),
        metadata={"env": "prod"},
    )


def deployment_spec() -> DeploymentSpec:
    return DeploymentSpec(
        name="Weekly scan",
        agent="agent_1",
        environment_id="env_1",
        initial_events=(
            UserMessage(content=(TextBlock(text="Run the weekly scan."),)),
        ),
        schedule=CronSchedule(expression="0 20 * * 5", timezone="UTC"),
        vault_ids=("vault_1",),
    )


@pytest.mark.asyncio
async def test_create_environment_uses_regular_key_beta_and_limited_network() -> None:
    seen: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen = request
        return httpx.Response(200, json=environment())

    client = adapter(handler)
    result = await client.create_environment(
        environment_spec(), idempotency_key="environment-create-1"
    )
    assert result.id == "env_1"
    assert seen is not None
    assert seen.headers["x-api-key"] == API_KEY
    assert seen.headers["anthropic-beta"] == MANAGED_AGENTS_BETA
    assert seen.headers["idempotency-key"] == "environment-create-1"
    assert json.loads(seen.content)["config"]["networking"]["type"] == "limited"
    assert API_KEY not in repr(vars(client))
    await client.aclose()


@pytest.mark.asyncio
async def test_create_deployment_binds_agent_environment_schedule_and_vault() -> None:
    seen: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen = request
        return httpx.Response(200, json=deployment())

    client = adapter(handler)
    result = await client.create_deployment(
        deployment_spec(), idempotency_key="deployment-create-1"
    )
    assert result.agent.version == 3
    body = json.loads(seen.content)  # type: ignore[union-attr]
    assert body["environment_id"] == "env_1"
    assert body["schedule"] == {
        "type": "cron",
        "expression": "0 20 * * 5",
        "timezone": "UTC",
    }
    assert body["vault_ids"] == ["vault_1"]
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("resource", ("environments", "deployments"))
async def test_lists_consume_opaque_pages_without_duplicates(resource: str) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        item = (
            environment(f"env_{calls}")
            if resource == "environments"
            else deployment(f"depl_{calls}")
        )
        if calls == 1:
            return httpx.Response(200, json={"data": [item], "next_page": "next"})
        assert request.url.params["page"] == "next"
        return httpx.Response(200, json={"data": [item], "next_page": None})

    client = adapter(handler)
    result = (
        await client.list_environments(page_size=1)
        if resource == "environments"
        else await client.list_deployments(page_size=1)
    )
    assert len(result) == 2
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ("duplicate", "empty", "repeat", "pages"))
async def test_pagination_failures_are_closed(failure: str) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        data = [] if failure == "empty" else [
            environment("env_same" if failure == "duplicate" else f"env_{calls}")
        ]
        token = "same" if failure == "repeat" else f"token-{calls}"
        return httpx.Response(200, json={"data": data, "next_page": token})

    client = adapter(handler)
    with pytest.raises(ManagedAgentAdapterError, match="duplicate|token|page"):
        await client.list_environments(page_size=1, max_pages=2)
    await client.aclose()


@pytest.mark.asyncio
async def test_lifecycle_actions_use_documented_non_destructive_paths() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/run"):
            return httpx.Response(
                200,
                json={
                    "id": "drun_1",
                    "type": "deployment_run",
                    "deployment_id": "depl_1",
                    "session_id": "session_1",
                    "created_at": "2026-07-01T00:00:00Z",
                },
            )
        return httpx.Response(
            200,
            json=deployment(
                status="paused" if request.url.path.endswith("/pause") else "active"
            ),
        )

    client = adapter(handler)
    await client.deployment_action("depl_1", "pause", idempotency_key="pause-1")
    await client.deployment_action("depl_1", "unpause", idempotency_key="unpause-1")
    run = await client.run_deployment("depl_1", idempotency_key="run-1")
    assert run.id == "drun_1"
    assert paths == [
        "/v1/deployments/depl_1/pause",
        "/v1/deployments/depl_1/unpause",
        "/v1/deployments/depl_1/run",
    ]
    assert not hasattr(client, "delete_environment")
    assert not hasattr(client, "delete_deployment")
    await client.aclose()


def test_production_specs_reject_unrestricted_network_and_bad_cron() -> None:
    with pytest.raises(ValidationError):
        CloudEnvironmentConfig.model_validate(
            {"type": "cloud", "networking": {"type": "unrestricted"}}
        )
    with pytest.raises(ValidationError):
        CronSchedule(expression="* * * *", timezone="UTC")
    with pytest.raises(ValidationError):
        LimitedNetwork(allowed_hosts=("api.example.com", "api.example.com"))


@pytest.mark.asyncio
async def test_wrong_credential_and_bad_inputs_fail_before_network() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    with pytest.raises(TypeError, match="regular-role"):
        AnthropicManagedAgentsAdapter(API_KEY)  # type: ignore[arg-type]
    client = adapter(handler)
    with pytest.raises(ValueError, match="resource type"):
        await client.get_environment("depl_1")
    with pytest.raises(ValueError, match="idempotency"):
        await client.create_environment(environment_spec(), idempotency_key="bad key")
    assert calls == 0
    await client.aclose()


@pytest.mark.asyncio
async def test_malformed_oversized_redirect_and_errors_are_sanitized() -> None:
    cases = [
        (lambda _: httpx.Response(200, json={**environment(), "unexpected": True}), "invalid"),
        (lambda _: httpx.Response(302, headers={"location": "https://elsewhere"}), "redirect"),
        (lambda _: httpx.Response(500, text="provider-secret"), "HTTP 500"),
    ]
    for handler, message in cases:
        client = adapter(handler)
        with pytest.raises(ManagedAgentAdapterError, match=message) as raised:
            await client.get_environment("env_1")
        assert "provider-secret" not in str(raised.value)
        await client.aclose()

    client = adapter(
        lambda _: httpx.Response(200, content=b"{" + b"x" * 2048),
        max_response_bytes=1024,
    )
    with pytest.raises(ManagedAgentAdapterError, match="byte limit"):
        await client.get_environment("env_1")
    await client.aclose()
