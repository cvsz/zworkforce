import json
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import SecretStr
from zeaz_enterprise.admin import (
    AdminAdapterError,
    AdminCredential,
    OpenAIAdminAdapter,
    ProjectStatus,
    UserRole,
)
from zeaz_enterprise.compliance import ComplianceCredential, ComplianceScope
from zeaz_enterprise.managed_agents import ManagedAgentCredential

ADMIN_KEY = "admin-test-secret-value"


def user(user_id: str = "user_1", *, role: str = "reader") -> dict:
    return {
        "object": "organization.user",
        "id": user_id,
        "name": "Test User",
        "email": "user@example.com",
        "role": role,
        "added_at": 1_721_471_533,
    }


def project(
    project_id: str = "proj_1",
    *,
    status: str = "active",
    name: str = "Test Project",
) -> dict:
    return {
        "object": "organization.project",
        "id": project_id,
        "name": name,
        "created_at": 1_721_471_533,
        "archived_at": 1_721_471_600 if status == "archived" else None,
        "status": status,
    }


def page(data: list[dict], *, has_more: bool = False) -> dict:
    return {
        "object": "list",
        "data": data,
        "first_id": data[0]["id"] if data else None,
        "last_id": data[-1]["id"] if data else None,
        "has_more": has_more,
    }


def adapter(handler, **changes) -> OpenAIAdminAdapter:
    values = {
        "credential": AdminCredential(
            provider="openai", secret=SecretStr(ADMIN_KEY)
        ),
        "organization": "org_1",
        "client": httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            trust_env=False,
        ),
    }
    values.update(changes)
    return OpenAIAdminAdapter(**values)


def test_admin_credential_role_and_provider_are_not_interchangeable() -> None:
    with pytest.raises(TypeError, match="OpenAI admin-role"):
        OpenAIAdminAdapter(  # type: ignore[arg-type]
            ComplianceCredential(
                secret=SecretStr(ADMIN_KEY),
                scopes={ComplianceScope.ORGANIZATION_DATA},
            ),
            organization="org_1",
        )
    with pytest.raises(TypeError, match="OpenAI admin-role"):
        OpenAIAdminAdapter(  # type: ignore[arg-type]
            ManagedAgentCredential(secret=SecretStr(ADMIN_KEY)),
            organization="org_1",
        )
    with pytest.raises(TypeError, match="OpenAI admin-role"):
        OpenAIAdminAdapter(
            AdminCredential(provider="anthropic", secret=SecretStr(ADMIN_KEY)),
            organization="org_1",
        )


@pytest.mark.asyncio
async def test_users_paginate_without_skips_and_use_admin_credential() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == f"Bearer {ADMIN_KEY}"
        if request.url.params.get("after") is None:
            return httpx.Response(200, json=page([user("user_1")], has_more=True))
        assert request.url.params["after"] == "user_1"
        return httpx.Response(200, json=page([user("user_2", role="owner")]))

    client = adapter(handler)
    users = await client.list_users(page_size=1)
    assert [item.id for item in users] == ["user_1", "user_2"]
    assert users[1].role is UserRole.OWNER
    assert users[0].added_at == datetime.fromtimestamp(1_721_471_533, tz=UTC)
    assert len(requests) == 2
    assert ADMIN_KEY not in repr(vars(client))
    await client.aclose()


@pytest.mark.asyncio
async def test_project_lifecycle_uses_exact_paths_and_idempotency() -> None:
    calls: list[tuple[str, str, str | None, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        calls.append(
            (
                request.method,
                request.url.path,
                request.headers.get("idempotency-key"),
                body,
            )
        )
        if request.url.path.endswith("/archive"):
            return httpx.Response(200, json=project(status="archived"))
        if request.method == "POST" and request.url.path.endswith("/proj_1"):
            return httpx.Response(200, json=project(name=body["name"]))
        if request.method == "POST":
            return httpx.Response(200, json=project())
        return httpx.Response(200, json=project())

    client = adapter(handler)
    created = await client.create_project(
        "Test Project",
        geography="us",
        idempotency_key="create-1",
    )
    updated = await client.update_project(
        created.id,
        "Renamed",
        idempotency_key="update-1",
    )
    archived = await client.archive_project(
        created.id,
        idempotency_key="archive-1",
    )
    assert updated.name == "Renamed"
    assert archived.status is ProjectStatus.ARCHIVED
    assert calls == [
        (
            "POST",
            "/v1/organization/projects",
            "create-1",
            {"name": "Test Project", "geography": "us"},
        ),
        (
            "POST",
            "/v1/organization/projects/proj_1",
            "update-1",
            {"name": "Renamed"},
        ),
        (
            "POST",
            "/v1/organization/projects/proj_1/archive",
            "archive-1",
            {},
        ),
    ]
    await client.aclose()


@pytest.mark.asyncio
async def test_get_and_update_user_role() -> None:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        role = (
            json.loads(request.content)["role"]
            if request.method == "POST"
            else "reader"
        )
        return httpx.Response(200, json=user(role=role))

    client = adapter(handler)
    assert (await client.get_user("user_1")).role is UserRole.READER
    changed = await client.update_user_role(
        "user_1",
        UserRole.OWNER,
        idempotency_key="role-1",
    )
    assert changed.role is UserRole.OWNER
    assert calls == [
        ("GET", "/v1/organization/users/user_1"),
        ("POST", "/v1/organization/users/user_1"),
    ]
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ("duplicate", "cursor", "empty", "pages"))
async def test_bad_pagination_fails_closed(failure: str) -> None:
    count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        if failure == "duplicate":
            payload = page([user("same")], has_more=count == 1)
        elif failure == "cursor":
            payload = page([user("same")], has_more=True)
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
@pytest.mark.parametrize(
    ("response", "match"),
    (
        (httpx.Response(302, headers={"location": "https://evil.example"}), "redirect"),
        (httpx.Response(200, content=b"not-json"), "invalid JSON"),
        (httpx.Response(200, json=[]), "non-object"),
        (httpx.Response(403, json={"error": {"message": ADMIN_KEY}}), "HTTP 403"),
    ),
)
async def test_transport_errors_are_sanitized(
    response: httpx.Response,
    match: str,
) -> None:
    client = adapter(lambda _: response)
    with pytest.raises(AdminAdapterError, match=match) as raised:
        await client.get_project("proj_1")
    assert ADMIN_KEY not in str(raised.value)
    await client.aclose()


@pytest.mark.asyncio
async def test_oversized_and_malformed_resources_fail_closed() -> None:
    oversized = adapter(
        lambda _: httpx.Response(200, content=b"{" + b"x" * 2048),
        max_response_bytes=1024,
    )
    with pytest.raises(AdminAdapterError, match="byte limit"):
        await oversized.get_user("user_1")
    await oversized.aclose()

    for payload in (
        {**project(), "status": "surprise"},
        {**project(), "unexpected": "field"},
        {**project(status="archived"), "archived_at": None},
    ):
        malformed = adapter(lambda _, body=payload: httpx.Response(200, json=body))
        with pytest.raises(AdminAdapterError, match="invalid project"):
            await malformed.get_project("proj_1")
        await malformed.aclose()


@pytest.mark.asyncio
async def test_invalid_inputs_fail_before_network() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    client = adapter(handler)
    with pytest.raises(AdminAdapterError, match="idempotency"):
        await client.create_project("name", idempotency_key="contains spaces")
    with pytest.raises(AdminAdapterError, match="identifier"):
        await client.get_user("../bad?")
    assert calls == 0
    await client.aclose()
