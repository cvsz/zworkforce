import hashlib
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from zeaz_control.adapters import (
    AnthropicModelAdapter,
    ControlAdapterError,
    OpenAIModelAdapter,
)
from zeaz_control.batches import BatchStatus, BatchSubmission
from zeaz_control.files import FilePurpose
from zeaz_control.models import ModelLifecycle

NOW = datetime(2026, 7, 26, tzinfo=UTC)


@pytest.mark.asyncio
async def test_openai_model_adapter_keeps_credentials_out_of_records() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {
                        "id": "gpt-test",
                        "object": "model",
                        "created": 123,
                        "owned_by": "system",
                    }
                ],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = OpenAIModelAdapter(
        "private-openai-key",
        account="project-a",
        client=client,
        clock=lambda: NOW,
    )
    page = await adapter.list_models(cursor=None, limit=100)
    assert page.items[0].model == "gpt-test"
    assert page.items[0].observed_at == NOW
    assert requests[0].headers["authorization"] == "Bearer private-openai-key"
    assert "private-openai-key" not in page.model_dump_json()
    await client.aclose()


@pytest.mark.asyncio
async def test_anthropic_model_adapter_uses_bounded_cursor_pagination() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "claude-test",
                        "type": "model",
                        "display_name": "Claude Test",
                        "created_at": "2026-01-01T00:00:00Z",
                        "status": "deprecated",
                    }
                ],
                "has_more": True,
                "last_id": "model-cursor",
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = AnthropicModelAdapter(
        "private-anthropic-key",
        client=client,
        clock=lambda: NOW,
    )
    page = await adapter.list_models(cursor="previous", limit=25)
    assert page.next_cursor == "model-cursor"
    assert page.items[0].lifecycle is ModelLifecycle.DEPRECATED
    assert requests[0].url.params["after_id"] == "previous"
    assert requests[0].url.params["limit"] == "25"
    assert requests[0].headers["x-api-key"] == "private-anthropic-key"
    assert "private-anthropic-key" not in page.model_dump_json()
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response,error_match",
    (
        (httpx.Response(302, headers={"location": "https://evil.test"}), "redirect"),
        (httpx.Response(401, json={"error": "private detail"}), "HTTP 401"),
        (httpx.Response(200, content=b"not-json"), "invalid JSON"),
        (
            httpx.Response(
                200,
                json={"data": [{"id": "a"}], "has_more": True},
            ),
            "cursor",
        ),
    ),
)
async def test_adapter_rejects_untrusted_responses_without_leaking_body(
    response: httpx.Response,
    error_match: str,
) -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: response))
    adapter = AnthropicModelAdapter("secret", client=client)
    with pytest.raises(ControlAdapterError, match=error_match) as raised:
        await adapter.list_models(cursor=None, limit=10)
    assert "private detail" not in str(raised.value)
    await client.aclose()


@pytest.mark.asyncio
async def test_adapter_rejects_excessive_response() -> None:
    response = httpx.Response(200, content=b"x" * 1025)
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: response))
    adapter = OpenAIModelAdapter(
        "secret",
        client=client,
        max_response_bytes=1024,
    )
    with pytest.raises(ControlAdapterError, match="byte limit"):
        await adapter.list_models(cursor=None, limit=10)
    await client.aclose()


@pytest.mark.parametrize(
    "url",
    (
        "http://api.example.com",
        "https://user:pass@api.example.com",
        "https://api.example.com?key=secret",
        "file:///tmp/provider",
    ),
)
def test_control_adapter_url_policy(url: str) -> None:
    with pytest.raises(ValueError):
        OpenAIModelAdapter("secret", base_url=url)


@pytest.mark.asyncio
async def test_openai_file_upload_download_and_delete_are_streamed(
    tmp_path: Path,
) -> None:
    content = b'{"custom_id":"one"}\n'
    upload = tmp_path / "upload.jsonl"
    upload.write_bytes(content)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            assert request.url.path == "/v1/files"
            assert request.headers["authorization"] == "Bearer private-key"
            assert "multipart/form-data" in request.headers["content-type"]
            assert b"private-key" not in request.content
            assert content in request.content
            return httpx.Response(
                200,
                json={
                    "id": "file-test",
                    "object": "file",
                    "bytes": len(content),
                    "created_at": 1_774_483_200,
                    "filename": "upload.jsonl",
                    "purpose": "batch",
                    "status": "processed",
                },
            )
        if request.method == "GET":
            return httpx.Response(200, content=content)
        return httpx.Response(
            200,
            json={"id": "file-test", "object": "file", "deleted": True},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = OpenAIModelAdapter("private-key", account="project-a", client=client)
    digest = hashlib.sha256(content).hexdigest()
    record = await adapter.upload_file(
        upload,
        filename="upload.jsonl",
        media_type="application/jsonl",
        purpose=FilePurpose.BATCH,
        sha256=digest,
    )
    assert record.id == "file-test"
    assert record.sha256 == digest
    assert "private-key" not in record.model_dump_json()
    downloaded = b"".join([chunk async for chunk in adapter.download_file(record.id)])
    assert downloaded == content
    await adapter.delete_file(record.id)
    assert [request.method for request in requests] == ["POST", "GET", "DELETE"]
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_file_metadata_mismatch_and_delete_nonconfirmation_fail(
    tmp_path: Path,
) -> None:
    upload = tmp_path / "upload.txt"
    upload.write_bytes(b"hello")
    responses = [
        httpx.Response(
            200,
            json={
                "id": "file-test",
                "bytes": 999,
                "created_at": 1,
                "filename": "upload.txt",
                "purpose": "user_data",
            },
        ),
        httpx.Response(200, json={"id": "file-test", "deleted": False}),
    ]
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: responses.pop(0))
    )
    adapter = OpenAIModelAdapter("secret", client=client)
    with pytest.raises(ControlAdapterError, match="metadata"):
        await adapter.upload_file(
            upload,
            filename="upload.txt",
            media_type="text/plain",
            purpose=FilePurpose.USER_DATA,
            sha256="0" * 64,
        )
    with pytest.raises(ControlAdapterError, match="confirm"):
        await adapter.delete_file("file-test")
    await client.aclose()


def openai_batch_payload(
    *,
    status: str = "in_progress",
    batch_id: str = "batch-test",
) -> dict:
    return {
        "id": batch_id,
        "object": "batch",
        "input_file_id": "file-test",
        "endpoint": "/v1/responses",
        "completion_window": "24h",
        "status": status,
        "created_at": 1_774_483_200,
        "in_progress_at": 1_774_483_201,
        "output_file_id": "file-output" if status == "completed" else None,
        "error_file_id": None,
        "request_counts": {"total": 2, "completed": 0, "failed": 0},
        "metadata": {"source": "test"},
    }


@pytest.mark.asyncio
async def test_openai_batch_lifecycle_and_idempotency_headers() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/v1/batches" and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": [openai_batch_payload()],
                    "has_more": True,
                    "last_id": "batch-test",
                },
            )
        if request.url.path.endswith("/cancel"):
            return httpx.Response(
                200,
                json=openai_batch_payload(status="cancelling"),
            )
        return httpx.Response(200, json=openai_batch_payload())

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = OpenAIModelAdapter("private-key", account="project-a", client=client)
    submission = BatchSubmission(
        provider="openai",
        account="project-a",
        input_file_id="file-test",
        endpoint="/v1/responses",
    )
    created = await adapter.submit_batch(submission, idempotency_key="create-key")
    assert created.status is BatchStatus.IN_PROGRESS
    page = await adapter.list_batches(cursor="prior", limit=25)
    assert page.next_cursor == "batch-test"
    retrieved = await adapter.get_batch("batch-test")
    assert retrieved.id == "batch-test"
    cancelled = await adapter.cancel_batch(
        "batch-test",
        idempotency_key="cancel-key",
    )
    assert cancelled.status is BatchStatus.CANCELLING
    assert requests[0].headers["idempotency-key"] == "create-key"
    assert requests[-1].headers["idempotency-key"] == "cancel-key"
    assert requests[1].url.params["after"] == "prior"
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_batch_results_parse_success_and_sanitized_error() -> None:
    output = (
        b'{"custom_id":"one","response":{"status_code":200,"body":{"ok":true}},'
        b'"error":null}\n'
        b'{"custom_id":"two","response":null,"error":{"code":"request_timeout",'
        b'"message":"private provider detail"}}\n'
    )
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=output))
    )
    adapter = OpenAIModelAdapter("secret", account="project-a", client=client)
    raw = openai_batch_payload(status="completed")
    raw["completed_at"] = 1_774_483_202
    raw["request_counts"] = {"total": 2, "completed": 1, "failed": 1}
    from zeaz_control.adapters import _openai_batch

    record = _openai_batch(raw, account="project-a")
    results = [item async for item in adapter.batch_results(record)]
    assert results[0].response == {"ok": True}
    assert results[1].error_code == "request_timeout"
    assert "private provider detail" not in results[1].model_dump_json()
    await client.aclose()
