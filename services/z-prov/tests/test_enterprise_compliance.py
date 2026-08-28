from datetime import UTC, datetime

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from zeaz_enterprise.compliance import (
    AnthropicComplianceAdapter,
    ComplianceAdapterError,
    ComplianceCredential,
    ComplianceScope,
)

COMPLIANCE_KEY = "anthropic-compliance-test-secret"
ORG_UUID = "abcdef01-2345-6789-abcd-ef0123456789"


def credential(*scopes: ComplianceScope) -> ComplianceCredential:
    return ComplianceCredential(
        secret=SecretStr(COMPLIANCE_KEY),
        scopes=frozenset(scopes),
    )


def organization(uuid: str = ORG_UUID) -> dict:
    return {
        "uuid": uuid,
        "name": "Example Organization",
        "created_at": "2026-04-10T08:09:10Z",
    }


def activity(activity_id: str = "activity_1") -> dict:
    return {
        "id": activity_id,
        "created_at": "2026-04-10T08:09:10Z",
        "organization_id": "org_1",
        "organization_uuid": ORG_UUID,
        "actor": {
            "type": "user_actor",
            "user_id": "user_1",
            "ip_address": "192.0.2.34",
        },
        "type": "claude_chat_created",
        "claude_chat_id": "chat_1",
    }


def adapter(handler, *scopes: ComplianceScope, **changes) -> AnthropicComplianceAdapter:
    values = {
        "credential": credential(*scopes),
        "client": httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            trust_env=False,
        ),
    }
    values.update(changes)
    return AnthropicComplianceAdapter(**values)


@pytest.mark.asyncio
async def test_organizations_use_opaque_pagination_and_compliance_key() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["x-api-key"] == COMPLIANCE_KEY
        if len(requests) == 1:
            assert "page" not in request.url.params
            return httpx.Response(
                200,
                json={
                    "data": [organization()],
                    "has_more": True,
                    "next_page": "opaque-token",
                },
            )
        assert request.url.params["page"] == "opaque-token"
        return httpx.Response(
            200,
            json={"data": [], "has_more": False, "next_page": None},
        )

    client = adapter(handler, ComplianceScope.ORGANIZATION_DATA)
    result = await client.list_organizations(page_size=1)
    assert result[0].name == "Example Organization"
    assert COMPLIANCE_KEY not in repr(vars(client))
    await client.aclose()


@pytest.mark.asyncio
async def test_activities_use_id_pagination_and_repeated_filters() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.params.get_list("activity_types[]") == [
            "claude_chat_created",
            "api_request",
        ]
        assert request.url.params.get_list("organization_ids[]") == ["org_1"]
        if len(requests) == 1:
            return httpx.Response(
                200,
                json={
                    "data": [activity()],
                    "has_more": True,
                    "first_id": "activity_1",
                    "last_id": "activity_1",
                },
            )
        assert request.url.params["after_id"] == "activity_1"
        return httpx.Response(
            200,
            json={
                "data": [activity("activity_2")],
                "has_more": False,
                "first_id": "activity_2",
                "last_id": "activity_2",
            },
        )

    client = adapter(handler, ComplianceScope.ACTIVITIES)
    result = await client.list_activities(
        activity_types=("claude_chat_created", "api_request"),
        organization_ids=("org_1",),
        created_at_gte=datetime(2026, 4, 1, tzinfo=UTC),
        created_at_lt=datetime(2026, 5, 1, tzinfo=UTC),
        page_size=1,
    )
    assert [item.id for item in result] == ["activity_1", "activity_2"]
    assert result[0].details == {"claude_chat_id": "chat_1"}
    assert requests[0].url.params["created_at.gte"].endswith("+00:00")
    await client.aclose()


@pytest.mark.asyncio
async def test_declared_scope_is_required_before_network() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    client = adapter(handler, ComplianceScope.USER_DATA)
    with pytest.raises(ComplianceAdapterError, match="scope"):
        await client.list_activities()
    with pytest.raises(ComplianceAdapterError, match="scope"):
        await client.list_organizations()
    assert calls == 0
    await client.aclose()


def test_credential_role_is_explicit_and_secrets_are_typed() -> None:
    with pytest.raises(TypeError, match="compliance-role"):
        AnthropicComplianceAdapter(COMPLIANCE_KEY)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ComplianceCredential(secret=SecretStr(""), scopes={ComplianceScope.ACTIVITIES})


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ("duplicate", "empty", "pages"))
async def test_activity_pagination_fails_closed(failure: str) -> None:
    count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        item = activity("same" if failure == "duplicate" else f"activity_{count}")
        data = [] if failure == "empty" else [item]
        return httpx.Response(
            200,
            json={
                "data": data,
                "has_more": True,
                "first_id": data[0]["id"] if data else None,
                "last_id": data[-1]["id"] if data else None,
            },
        )

    client = adapter(handler, ComplianceScope.ACTIVITIES)
    with pytest.raises(ComplianceAdapterError, match="duplicate|cursor|page"):
        await client.list_activities(page_size=1, max_pages=2)
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ("repeat", "empty", "pages"))
async def test_opaque_pagination_fails_closed(failure: str) -> None:
    count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        data = [] if failure == "empty" else [organization(f"{count:08x}-2345-6789-abcd-ef0123456789")]
        token = "same" if failure == "repeat" else f"token-{count}"
        return httpx.Response(
            200,
            json={"data": data, "has_more": True, "next_page": token},
        )

    client = adapter(handler, ComplianceScope.ORGANIZATION_DATA)
    with pytest.raises(ComplianceAdapterError, match="token|page"):
        await client.list_organizations(page_size=1, max_pages=2)
    await client.aclose()


@pytest.mark.asyncio
async def test_malformed_oversized_redirect_and_error_responses_are_sanitized() -> None:
    cases = [
        (lambda _: httpx.Response(200, json={**activity(), "actor": []}), "invalid"),
        (lambda _: httpx.Response(200, json={"data": []}), "invalid page"),
        (lambda _: httpx.Response(302, headers={"location": "https://elsewhere"}), "redirect"),
        (lambda _: httpx.Response(500, text="provider-secret-detail"), "HTTP 500"),
    ]
    for handler, message in cases:
        client = adapter(handler, ComplianceScope.ACTIVITIES)
        with pytest.raises(ComplianceAdapterError, match=message) as raised:
            await client.list_activities()
        assert "provider-secret-detail" not in str(raised.value)
        await client.aclose()

    client = adapter(
        lambda _: httpx.Response(200, content=b"{" + b"x" * 2048),
        ComplianceScope.ACTIVITIES,
        max_response_bytes=1024,
    )
    with pytest.raises(ComplianceAdapterError, match="byte limit"):
        await client.list_activities()
    await client.aclose()


@pytest.mark.asyncio
async def test_invalid_filters_fail_before_network_and_deletion_is_absent() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    client = adapter(handler, ComplianceScope.ACTIVITIES)
    with pytest.raises(ValueError):
        await client.list_activities(activity_types=("Bad Type",))
    with pytest.raises(ValueError):
        await client.list_activities(created_at_gte=datetime(2026, 1, 1))
    with pytest.raises(ValueError):
        await client.list_activities(
            created_at_gte=datetime(2026, 2, 1, tzinfo=UTC),
            created_at_lt=datetime(2026, 1, 1, tzinfo=UTC),
        )
    assert calls == 0
    assert not hasattr(client, "delete_activity")
    await client.aclose()
