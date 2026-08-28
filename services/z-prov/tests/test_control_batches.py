import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from zeaz_control.batches import (
    BatchCounts,
    BatchPage,
    BatchRecord,
    BatchResult,
    BatchService,
    BatchStatus,
    BatchSubmission,
    ControlBatchError,
    IdempotencyConflict,
)
from zeaz_control.files import FilePurpose, FileRecord
from zeaz_control.models import ControlStore

NOW = datetime(2026, 7, 26, tzinfo=UTC)


class FakeBatchAdapter:
    provider = "openai"
    account = "project-a"

    def __init__(self) -> None:
        self.submit_calls: list[str] = []
        self.cancel_calls: list[str] = []
        self.pages: list[BatchPage] = []
        self.fail_submit = False
        self.results: tuple[BatchResult, ...] = ()

    async def submit_batch(
        self,
        submission: BatchSubmission,
        *,
        idempotency_key: str,
    ) -> BatchRecord:
        self.submit_calls.append(idempotency_key)
        if self.fail_submit:
            self.fail_submit = False
            raise ControlBatchError("temporary provider failure")
        return batch(
            "batch-created",
            input_file_id=submission.input_file_id,
            endpoint=submission.endpoint,
        )

    async def list_batches(self, *, cursor, limit) -> BatchPage:
        del cursor, limit
        return self.pages.pop(0)

    async def get_batch(self, batch_id: str) -> BatchRecord:
        return batch(batch_id, status=BatchStatus.COMPLETED)

    async def cancel_batch(
        self,
        batch_id: str,
        *,
        idempotency_key: str,
    ) -> BatchRecord:
        self.cancel_calls.append(idempotency_key)
        return batch(batch_id, status=BatchStatus.CANCELLING)

    async def batch_results(self, record: BatchRecord):
        del record
        for item in self.results:
            yield item


def batch(
    batch_id: str,
    *,
    input_file_id: str = "file-batch",
    endpoint: str = "/v1/responses",
    status: BatchStatus = BatchStatus.IN_PROGRESS,
    updated_at: datetime = NOW,
) -> BatchRecord:
    return BatchRecord(
        provider="openai",
        account="project-a",
        id=batch_id,
        input_file_id=input_file_id,
        endpoint=endpoint,
        status=status,
        counts=BatchCounts(total=2, completed=0, failed=0),
        created_at=NOW,
        updated_at=updated_at,
    )


def submission(
    *,
    input_file_id: str = "file-batch",
    endpoint: str = "/v1/responses",
) -> BatchSubmission:
    return BatchSubmission(
        provider="openai",
        account="project-a",
        input_file_id=input_file_id,
        endpoint=endpoint,
    )


def setup_service(
    tmp_path: Path,
    *,
    file_purpose: FilePurpose = FilePurpose.BATCH,
    max_result_count: int = 100,
    max_result_bytes: int = 1024 * 1024,
) -> tuple[BatchService, FakeBatchAdapter, ControlStore]:
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    store = ControlStore(state / "control.sqlite3")
    with store._connect() as connection:
        connection.execute(
            "CREATE TABLE control_files ("
            "provider TEXT NOT NULL, account TEXT NOT NULL, id TEXT NOT NULL, "
            "payload BLOB NOT NULL, PRIMARY KEY(provider, account, id))"
        )
        record = FileRecord(
            provider="openai",
            account="project-a",
            id="file-batch",
            filename="requests.jsonl",
            bytes=10,
            sha256=hashlib.sha256(b"x" * 10).hexdigest(),
            media_type="application/jsonl",
            purpose=file_purpose,
            created_at=NOW,
        )
        connection.execute(
            "INSERT INTO control_files VALUES (?, ?, ?, ?)",
            ("openai", "project-a", "file-batch", record.model_dump_json().encode()),
        )
        connection.commit()
    adapter = FakeBatchAdapter()
    return (
        BatchService(
            store,
            {"openai": adapter},
            max_result_count=max_result_count,
            max_result_bytes=max_result_bytes,
        ),
        adapter,
        store,
    )


@pytest.mark.asyncio
async def test_submit_is_durably_idempotent_and_transactionally_audited(
    tmp_path: Path,
) -> None:
    service, adapter, store = setup_service(tmp_path)
    first = await service.submit(
        submission(),
        idempotency_key="create-1",
        now=NOW,
    )
    second = await service.submit(
        submission(),
        idempotency_key="create-1",
        now=NOW + timedelta(seconds=1),
    )
    assert first == second
    assert adapter.submit_calls == ["create-1"]
    assert service.get("openai", "project-a", first.id) == first
    audit = store.audit()
    assert [event.event_type for event in audit] == ["control.batch.created"]
    assert "create-1" not in audit[0].model_dump_json()


@pytest.mark.asyncio
async def test_idempotency_key_payload_conflict_fails_before_provider(
    tmp_path: Path,
) -> None:
    service, adapter, _ = setup_service(tmp_path)
    await service.submit(submission(), idempotency_key="same")
    with pytest.raises(IdempotencyConflict, match="payload"):
        await service.submit(
            submission(endpoint="/v1/chat/completions"),
            idempotency_key="same",
        )
    assert adapter.submit_calls == ["same"]


@pytest.mark.asyncio
async def test_pending_provider_failure_retries_with_same_idempotency_key(
    tmp_path: Path,
) -> None:
    service, adapter, _ = setup_service(tmp_path)
    adapter.fail_submit = True
    with pytest.raises(ControlBatchError, match="temporary"):
        await service.submit(submission(), idempotency_key="retry-key")
    record = await service.submit(submission(), idempotency_key="retry-key")
    assert record.id == "batch-created"
    assert adapter.submit_calls == ["retry-key", "retry-key"]


@pytest.mark.asyncio
async def test_invalid_idempotency_key_fails_before_provider(tmp_path: Path) -> None:
    service, adapter, _ = setup_service(tmp_path)
    with pytest.raises(ControlBatchError, match="idempotency key"):
        await service.submit(submission(), idempotency_key="contains spaces")
    assert adapter.submit_calls == []


@pytest.mark.asyncio
async def test_cancel_is_idempotent_and_updates_catalog(tmp_path: Path) -> None:
    service, adapter, store = setup_service(tmp_path)
    created = await service.submit(submission(), idempotency_key="create")
    first = await service.cancel(
        "openai",
        "project-a",
        created.id,
        idempotency_key="cancel-1",
    )
    second = await service.cancel(
        "openai",
        "project-a",
        created.id,
        idempotency_key="cancel-1",
    )
    assert first == second
    assert first.status is BatchStatus.CANCELLING
    assert adapter.cancel_calls == ["cancel-1"]
    assert [event.event_type for event in store.audit()] == [
        "control.batch.created",
        "control.batch.cancelled",
    ]


@pytest.mark.asyncio
async def test_refresh_pages_then_commits_without_skips_or_duplicates(
    tmp_path: Path,
) -> None:
    service, adapter, _ = setup_service(tmp_path)
    adapter.pages = [
        BatchPage(items=(batch("batch-a"),), next_cursor="cursor-a"),
        BatchPage(items=(batch("batch-b"),)),
    ]
    assert await service.refresh("openai", page_size=1, now=NOW) == 2
    assert [item.id for item in service.list("openai", "project-a").items] == [
        "batch-a",
        "batch-b",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ("duplicate", "cursor", "pages"))
async def test_bad_provider_pagination_never_partially_commits(
    tmp_path: Path,
    failure: str,
) -> None:
    service, adapter, store = setup_service(tmp_path)
    if failure == "duplicate":
        adapter.pages = [
            BatchPage(items=(batch("batch-a"),), next_cursor="next"),
            BatchPage(items=(batch("batch-a"),)),
        ]
        kwargs = {}
    elif failure == "cursor":
        adapter.pages = [
            BatchPage(items=(), next_cursor="same"),
            BatchPage(items=(), next_cursor="same"),
        ]
        kwargs = {}
    else:
        adapter.pages = [
            BatchPage(items=(), next_cursor="a"),
            BatchPage(items=(), next_cursor="b"),
        ]
        kwargs = {"max_pages": 2}
    with pytest.raises(ControlBatchError):
        await service.refresh("openai", **kwargs)
    assert service.list("openai", "project-a").items == ()
    assert store.audit() == ()


@pytest.mark.asyncio
async def test_refresh_rejects_stale_and_terminal_regressions(tmp_path: Path) -> None:
    service, adapter, store = setup_service(tmp_path)
    adapter.pages = [
        BatchPage(
            items=(
                batch(
                    "batch-a",
                    status=BatchStatus.COMPLETED,
                    updated_at=NOW + timedelta(seconds=1),
                ),
            )
        ),
    ]
    await service.refresh("openai", now=NOW)
    for bad in (
        batch(
            "batch-a",
            status=BatchStatus.COMPLETED,
            updated_at=NOW,
        ),
        batch(
            "batch-a",
            status=BatchStatus.IN_PROGRESS,
            updated_at=NOW + timedelta(seconds=2),
        ),
    ):
        adapter.pages = [BatchPage(items=(bad,))]
        with pytest.raises(ControlBatchError, match="stale|terminal"):
            await service.refresh("openai")
    assert service.get("openai", "project-a", "batch-a").status is BatchStatus.COMPLETED
    assert len(store.audit()) == 1


@pytest.mark.asyncio
async def test_results_reject_duplicates_wrong_batch_and_limits(tmp_path: Path) -> None:
    service, adapter, _ = setup_service(tmp_path, max_result_count=1)
    created = await service.submit(submission(), idempotency_key="create")
    good = BatchResult(
        batch_id=created.id,
        custom_id="request-1",
        status_code=200,
        response={"output": "ok"},
    )
    adapter.results = (good,)
    assert [item async for item in service.results("openai", "project-a", created.id)] == [
        good
    ]
    adapter.results = (good, good)
    with pytest.raises(ControlBatchError, match="duplicate|limit"):
        async for _ in service.results("openai", "project-a", created.id):
            pass
    adapter.results = (
        good.model_copy(update={"batch_id": "different"}),
    )
    with pytest.raises(ControlBatchError, match="another batch"):
        async for _ in service.results("openai", "project-a", created.id):
            pass


@pytest.mark.asyncio
async def test_submit_requires_catalogued_batch_purpose_file(tmp_path: Path) -> None:
    service, adapter, _ = setup_service(
        tmp_path,
        file_purpose=FilePurpose.USER_DATA,
    )
    with pytest.raises(ControlBatchError, match="wrong purpose"):
        await service.submit(submission(), idempotency_key="create")
    assert adapter.submit_calls == []
