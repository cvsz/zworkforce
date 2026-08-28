import json

import httpx
import pytest
from pydantic import SecretStr
from zeaz_enterprise.admin import (
    AdminAdapterError,
    AdminCredential,
    AnthropicAdminAdapter,
    AnthropicAssignableRole,
    AnthropicUserRole,
)

ADMIN_KEY = "anthropic-admin-test-secret"


def user(user_id: str = "user_1", *, role: str = "user") -> dict:
    return {
        "type": "user",
        "id": user_id,
        "name": "Jane Doe",
        "email": "jane@example.com",
        "role": role,
        "added_at": "2026-06-12T09:14:03Z",
    }


def workspace(
    workspace_id: str = "wrkspc_1",
    *,
    name: str = "Production",
    archived: bool = False,
) -> dict:
    return {
        "type": "workspace",
        "id": workspace_id,
        "name": name,
        "display_color": "#6C5BB9",
        "compartment_id": "compartment-1",
        "external_key_id": None,
        "created_at": "2026-06-12T09:14:03Z",
        "archived_at": "2026-07-01T10:00:00Z" if archived else None,
        "data_residency": {
            "allowed_inference_geos": "unrestricted",
            "default_inference_geo": "global",
            "workspace_geo": "us",
        },
        "tags": {"env": "prod"},
    }


def page(data: list[dict], *, has_more: bool = False) -> dict:
    return {
        "data": data,
        "first_id": data[0]["id"] if data else None,
        "last_id": data[-1]["id"] if data else None,
        "has_more": has_more,
    }


def adapter(handler, **changes) -> AnthropicAdminAdapter:
    values = {
        "credential": AdminCredential(
            provider="anthropic", secret=SecretStr(ADMIN_KEY)
        ),
        "organization": "org_1",
        "client": httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            trust_env=False,
        ),
    }
    values.update(changes)
    return AnthropicAdminAdapter(**values)


@pytest.mark.asyncio
async def test_users_paginate_with_after_id_and_dedicated_admin_key() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["x-api-key"] == ADMIN_KEY
        assert request.headers["anthropic-version"] == "2023-06-01"
        if request.url.params.get("after_id") is None:
            return httpx.Response(200, json=page([user("user_1")], has_more=True))
        assert request.url.params["after_id"] == "user_1"
        return httpx.Response(200, json=page([user("user_2", role="owner")]))

    client = adapter(handler)
    users = await client.list_users(page_size=1)
    assert [item.id for item in users] == ["user_1", "user_2"]
    assert users[1].role is AnthropicUserRole.OWNER
    assert len(requests) == 2
    assert ADMIN_KEY not in repr(vars(client))
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_and_assignable_role_update() -> None:
    seen: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen = request
        return httpx.Response(
            200,
            json=user(role=json.loads(request.content)["role"]),
        )

    client = adapter(handler, auth_kind="oauth")
    changed = await client.update_user_role(
        "user_1",
        AnthropicAssignableRole.MANAGED,
        idempotency_key="role-1",
    )
    assert changed.role is AnthropicUserRole.MANAGED
    assert seen is not None
    assert seen.headers["authorization"] == f"Bearer {ADMIN_KEY}"
    assert "x-api-key" not in seen.headers
    assert seen.headers["idempotency-key"] == "role-1"
    await client.aclose()


@pytest.mark.asyncio
async def test_workspace_lifecycle_uses_documented_paths() -> None:
    calls: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        calls.append((request.method, request.url.path, body))
        return httpx.Response(
            200,
            json=workspace(
                name=(body or {}).get("name", "Production"),
                archived=request.url.path.endswith("/archive"),
            ),
        )

    client = adapter(handler)
    assert (await client.create_workspace(
        "Production",
        idempotency_key="create-1",
    )).name == "Production"
    assert (await client.update_workspace(
        "wrkspc_1",
        "Renamed",
        idempotency_key="update-1",
    )).name == "Renamed"
    assert (await client.archive_workspace(
        "wrkspc_1",
        idempotency_key="archive-1",
    )).archived_at is not None
    assert calls == [
        ("POST", "/v1/organizations/workspaces", {"name": "Production"}),
        ("POST", "/v1/organizations/workspaces/wrkspc_1", {"name": "Renamed"}),
        ("POST", "/v1/organizations/workspaces/wrkspc_1/archive", {}),
    ]
    await client.aclose()


@pytest.mark.asyncio
async def test_list_and_get_workspaces() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("workspaces"):
            assert request.url.params["include_archived"] == "true"
            return httpx.Response(200, json=page([workspace()]))
        return httpx.Response(200, json=workspace())

    client = adapter(handler)
    assert len(await client.list_workspaces(include_archived=True)) == 1
    assert (await client.get_workspace("wrkspc_1")).id == "wrkspc_1"
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ("duplicate", "empty", "pages"))
async def test_anthropic_bad_pagination_fails_closed(failure: str) -> None:
    count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        if failure == "duplicate":
            payload = page([user("same")], has_more=count == 1)
        elif failure == "empty":
            payload = page([], has_more=True)
        else:
            payload = page([user(f"user_{count}")], has_more=True)
        return httpx.Response(200, json=payload)

    client = adapter(handler)
    with pytest.raises(AdminAdapterError, match="duplicate|cursor|page"):
        await client.list_users(page_size=1, max_pages=2)
    await client.aclose()


@pytest.mark.asyncio
async def test_anthropic_malformed_and_oversized_responses_fail_closed() -> None:
    for payload in (
        {**user(), "role": "root"},
        {**user(), "unexpected": True},
        {**workspace(), "display_color": "purple"},
        {**workspace(), "tags": {"anthropic.internal": "bad"}},
    ):
        client = adapter(lambda _, body=payload: httpx.Response(200, json=body))
        with pytest.raises(AdminAdapterError, match="invalid"):
            if payload.get("type") == "user":
                await client.get_user("user_1")
            else:
                await client.get_workspace("wrkspc_1")
        await client.aclose()

    oversized = adapter(
        lambda _: httpx.Response(200, content=b"{" + b"x" * 2048),
        max_response_bytes=1024,
    )
    with pytest.raises(AdminAdapterError, match="byte limit"):
        await oversized.get_user("user_1")
    await oversized.aclose()


@pytest.mark.asyncio
async def test_nonassignable_role_and_invalid_key_fail_before_network() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    client = adapter(handler)
    with pytest.raises(AdminAdapterError, match="not assignable"):
        await client.update_user_role(
            "user_1",
            "owner",  # type: ignore[arg-type]
            idempotency_key="role-1",
        )
    with pytest.raises(AdminAdapterError, match="idempotency"):
        await client.create_workspace("name", idempotency_key="bad key")
    assert calls == 0
    await client.aclose()
