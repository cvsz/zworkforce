import json

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from zeaz_enterprise.agent_memory import (
    DREAMING_BETA,
    MEMORY_BETA,
    AgentMemoryAdapterError,
    AnthropicAgentMemoryAdapter,
    DreamSpec,
    MemoryStoreSpec,
    OutcomeSpec,
    TextRubric,
)
from zeaz_enterprise.managed_agents import MANAGED_AGENTS_BETA, ManagedAgentCredential

KEY = "regular-agent-memory-test-key"


def store(store_id: str = "memstore_1", *, archived: bool = False) -> dict:
    return {
        "id": store_id,
        "type": "memory_store",
        "name": "Preferences",
        "description": "User preferences",
        "metadata": {"tenant": "one"},
        "created_at": "2026-07-01T00:00:00Z",
        "updated_at": "2026-07-02T00:00:00Z",
        "archived_at": "2026-07-03T00:00:00Z" if archived else None,
    }


def dream(dream_id: str = "drm_1", *, status: str = "pending") -> dict:
    return {
        "id": dream_id,
        "type": "dream",
        "status": status,
        "inputs": [
            {"type": "memory_store", "memory_store_id": "memstore_1"},
            {"type": "sessions", "session_ids": ["session_1", "session_2"]},
        ],
        "outputs": (
            [{"type": "memory_store", "memory_store_id": "memstore_2"}]
            if status != "pending"
            else []
        ),
        "model": {"id": "claude-opus-4-8"},
        "instructions": "Keep stable preferences.",
        "session_id": None,
        "created_at": "2026-07-01T00:00:00Z",
        "ended_at": None,
        "archived_at": None,
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
        "error": None,
    }


def adapter(handler, **changes) -> AnthropicAgentMemoryAdapter:
    values = {
        "credential": ManagedAgentCredential(secret=SecretStr(KEY)),
        "client": httpx.AsyncClient(
            transport=httpx.MockTransport(handler), trust_env=False
        ),
    }
    values.update(changes)
    return AnthropicAgentMemoryAdapter(**values)


@pytest.mark.asyncio
async def test_memory_store_uses_only_memory_beta_and_idempotency() -> None:
    seen: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen = request
        return httpx.Response(200, json=store())

    client = adapter(handler)
    result = await client.create_memory_store(
        MemoryStoreSpec(name="Preferences", description="User preferences"),
        idempotency_key="store-create-1",
    )
    assert result.id == "memstore_1"
    assert seen is not None
    assert seen.headers["anthropic-beta"] == MEMORY_BETA
    assert MANAGED_AGENTS_BETA not in seen.headers["anthropic-beta"]
    assert seen.headers["idempotency-key"] == "store-create-1"
    assert KEY not in repr(vars(client))
    await client.aclose()


@pytest.mark.asyncio
async def test_outcome_event_is_bounded_and_uses_managed_agents_beta() -> None:
    seen: httpx.Request | None = None
    spec = OutcomeSpec(
        description="Produce a verified report.",
        rubric=TextRubric(content="Check every citation."),
        max_iterations=5,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen = request
        event = {
            "id": "sevt_1",
            "outcome_id": "outc_1",
            "processed_at": "2026-07-01T00:00:00Z",
            **spec.model_dump(mode="json"),
        }
        return httpx.Response(200, json={"data": [event]})

    client = adapter(handler)
    result = await client.define_outcome(
        "session_1", spec, idempotency_key="outcome-1"
    )
    assert result.outcome_id == "outc_1"
    assert seen is not None
    assert seen.headers["anthropic-beta"] == MANAGED_AGENTS_BETA
    assert json.loads(seen.content) == {"events": [spec.model_dump(mode="json")]}
    await client.aclose()


@pytest.mark.asyncio
async def test_dream_uses_both_betas_and_exact_inputs() -> None:
    seen: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen = request
        return httpx.Response(200, json=dream())

    client = adapter(handler)
    result = await client.create_dream(
        DreamSpec(
            memory_store_id="memstore_1",
            session_ids=("session_1", "session_2"),
            model="claude-opus-4-8",
            instructions="Keep stable preferences.",
        ),
        idempotency_key="dream-1",
    )
    assert result.status == "pending"
    assert seen is not None
    assert seen.headers["anthropic-beta"] == f"{MANAGED_AGENTS_BETA},{DREAMING_BETA}"
    assert json.loads(seen.content)["inputs"] == [
        {"type": "memory_store", "memory_store_id": "memstore_1"},
        {"type": "sessions", "session_ids": ["session_1", "session_2"]},
    ]
    await client.aclose()


@pytest.mark.asyncio
async def test_dream_cancel_and_archive_use_documented_paths() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, json=dream(status="canceled"))

    client = adapter(handler)
    await client.dream_action("drm_1", "cancel", idempotency_key="cancel-1")
    await client.dream_action("drm_1", "archive", idempotency_key="archive-1")
    assert paths == ["/v1/dreams/drm_1/cancel", "/v1/dreams/drm_1/archive"]
    assert not hasattr(client, "delete_memory_store")
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ("store", "dream"))
async def test_lists_paginate_without_gaps_or_duplicates(kind: str) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        item = (
            store(f"memstore_{calls}")
            if kind == "store"
            else dream(f"drm_{calls}")
        )
        return httpx.Response(
            200,
            json={"data": [item], "next_page": "next" if calls == 1 else None},
        )

    client = adapter(handler)
    result = (
        await client.list_memory_stores(page_size=1)
        if kind == "store"
        else await client.list_dreams(page_size=1)
    )
    assert len(result) == 2
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ("duplicate", "empty", "repeat", "pages"))
async def test_bad_pagination_fails_closed(failure: str) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        data = [] if failure == "empty" else [
            store("memstore_same" if failure == "duplicate" else f"memstore_{calls}")
        ]
        token = "same" if failure == "repeat" else f"token-{calls}"
        return httpx.Response(200, json={"data": data, "next_page": token})

    client = adapter(handler)
    with pytest.raises(AgentMemoryAdapterError, match="duplicate|token|page"):
        await client.list_memory_stores(page_size=1, max_pages=2)
    await client.aclose()


def test_specs_enforce_bounds_and_unique_dream_sessions() -> None:
    with pytest.raises(ValidationError):
        OutcomeSpec(
            description="x",
            rubric=TextRubric(content="x"),
            max_iterations=21,
        )
    with pytest.raises(ValidationError, match="unique"):
        DreamSpec(
            memory_store_id="memstore_1",
            session_ids=("session_1", "session_1"),
            model="claude-opus-4-8",
        )


@pytest.mark.asyncio
async def test_malformed_redirect_size_and_errors_are_sanitized() -> None:
    cases = [
        (lambda _: httpx.Response(200, json={**store(), "extra": True}), "invalid"),
        (lambda _: httpx.Response(302, headers={"location": "https://elsewhere"}), "redirect"),
        (lambda _: httpx.Response(500, text="provider-secret"), "HTTP 500"),
    ]
    for handler, message in cases:
        client = adapter(handler)
        with pytest.raises(AgentMemoryAdapterError, match=message) as raised:
            await client.get_memory_store("memstore_1")
        assert "provider-secret" not in str(raised.value)
        await client.aclose()

    client = adapter(
        lambda _: httpx.Response(200, content=b"{" + b"x" * 2048),
        max_response_bytes=1024,
    )
    with pytest.raises(AgentMemoryAdapterError, match="byte limit"):
        await client.get_dream("drm_1")
    await client.aclose()
