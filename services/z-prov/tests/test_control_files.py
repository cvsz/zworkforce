import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from zeaz_control.files import (
    ControlFileError,
    ControlFileService,
    FilePolicy,
    FilePurpose,
    FileRecord,
)
from zeaz_control.models import ControlStore

NOW = datetime(2026, 7, 26, tzinfo=UTC)


class FakeFileAdapter:
    provider = "openai"
    account = "project-a"

    def __init__(self) -> None:
        self.uploaded: bytes | None = None
        self.records: dict[str, FileRecord] = {}
        self.deleted: list[str] = []
        self.download_chunks: tuple[bytes, ...] | None = None

    async def upload_file(
        self,
        path: Path,
        *,
        filename: str,
        media_type: str,
        purpose: FilePurpose,
        sha256: str,
    ) -> FileRecord:
        self.uploaded = path.read_bytes()
        record = FileRecord(
            provider=self.provider,
            account=self.account,
            id=f"file-{len(self.records):04d}",
            filename=filename,
            bytes=len(self.uploaded),
            sha256=sha256,
            media_type=media_type,
            purpose=purpose,
            created_at=NOW,
            extensions={"openai": {"status": "processed"}},
        )
        self.records[record.id] = record
        return record

    async def download_file(self, file_id: str):
        chunks = self.download_chunks
        if chunks is None:
            chunks = (self.uploaded or b"",)
        for chunk in chunks:
            yield chunk

    async def delete_file(self, file_id: str) -> None:
        self.deleted.append(file_id)


async def chunks(*values: bytes):
    for value in values:
        yield value


def service(
    tmp_path: Path,
    *,
    policy: FilePolicy | None = None,
) -> tuple[ControlFileService, FakeFileAdapter, ControlStore]:
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    control = ControlStore(state / "control.sqlite3")
    adapter = FakeFileAdapter()
    return (
        ControlFileService(control, {"openai": adapter}, policy=policy),
        adapter,
        control,
    )


@pytest.mark.asyncio
async def test_batch_jsonl_upload_is_streamed_validated_and_audited(
    tmp_path: Path,
) -> None:
    files, adapter, control = service(tmp_path)
    first = json.dumps(
        {
            "custom_id": "request-1",
            "method": "POST",
            "url": "/v1/responses",
            "body": {"model": "gpt-test", "input": "hello"},
        }
    ).encode() + b"\n"
    second = json.dumps(
        {
            "custom_id": "request-2",
            "method": "POST",
            "url": "/v1/responses",
            "body": {"model": "gpt-test", "input": "world"},
        }
    ).encode() + b"\n"
    record = await files.upload(
        "openai",
        chunks(first[:10], first[10:] + second),
        filename="requests.jsonl",
        media_type="application/jsonl",
        purpose=FilePurpose.BATCH,
        now=NOW,
    )
    assert adapter.uploaded == first + second
    assert record.sha256 == hashlib.sha256(first + second).hexdigest()
    assert files.get("openai", "project-a", record.id) == record
    assert control.audit()[0].event_type == "control.file.created"
    assert not list((tmp_path / "state/file-staging").iterdir())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename,media_type,purpose,data,match",
    (
        (
            "../escape.jsonl",
            "application/jsonl",
            FilePurpose.BATCH,
            b"{}\n",
            "basename",
        ),
        (
            "file.pdf",
            "application/pdf",
            FilePurpose.USER_DATA,
            b"not-pdf",
            "signature",
        ),
        (
            "file.jsonl",
            "application/jsonl",
            FilePurpose.BATCH,
            b"not-json\n",
            "invalid line",
        ),
        (
            "file.jsonl",
            "application/jsonl",
            FilePurpose.BATCH,
            b'{"custom_id":"a"}\n',
            "request shape",
        ),
        (
            "file.txt",
            "text/plain",
            FilePurpose.USER_DATA,
            b"\xff",
            "UTF-8",
        ),
    ),
)
async def test_invalid_name_mime_or_content_never_reaches_provider(
    tmp_path: Path,
    filename: str,
    media_type: str,
    purpose: FilePurpose,
    data: bytes,
    match: str,
) -> None:
    files, adapter, _ = service(tmp_path)
    with pytest.raises((ValueError, ControlFileError), match=match):
        await files.upload(
            "openai",
            chunks(data),
            filename=filename,
            media_type=media_type,
            purpose=purpose,
        )
    assert adapter.uploaded is None


@pytest.mark.asyncio
async def test_upload_byte_chunk_line_and_count_limits_cleanup_staging(
    tmp_path: Path,
) -> None:
    policy = FilePolicy(
        max_upload_bytes=1024,
        max_chunk_bytes=1024,
        max_jsonl_line_bytes=128,
        max_jsonl_lines=2,
    )
    files, adapter, _ = service(tmp_path, policy=policy)
    cases = (
        chunks(),
        chunks(b"x" * 1024, b"x"),
        chunks(b"x" * 1025),
        chunks(b'{"value":"' + b"x" * 200 + b'"}\n'),
        chunks(b"{}\n{}\n{}\n"),
    )
    for index, source in enumerate(cases):
        with pytest.raises(ControlFileError):
            await files.upload(
                "openai",
                source,
                filename=f"case-{index}.jsonl",
                media_type="application/jsonl",
                purpose=FilePurpose.EVALS,
            )
    assert adapter.uploaded is None
    assert not list((tmp_path / "state/file-staging").iterdir())


@pytest.mark.asyncio
async def test_download_is_bounded_and_integrity_checked(tmp_path: Path) -> None:
    files, adapter, _ = service(tmp_path)
    content = b"safe text"
    record = await files.upload(
        "openai",
        chunks(content),
        filename="file.txt",
        media_type="text/plain",
        purpose=FilePurpose.USER_DATA,
    )
    downloaded = b"".join(
        [
            chunk
            async for chunk in files.download(
                "openai",
                "project-a",
                record.id,
            )
        ]
    )
    assert downloaded == content
    adapter.download_chunks = (b"tampered",)
    with pytest.raises(ControlFileError, match="integrity"):
        async for _ in files.download("openai", "project-a", record.id):
            pass


@pytest.mark.asyncio
async def test_download_rejects_excessive_chunk_before_yield(tmp_path: Path) -> None:
    policy = FilePolicy(max_chunk_bytes=1024)
    files, adapter, _ = service(tmp_path, policy=policy)
    record = await files.upload(
        "openai",
        chunks(b"safe"),
        filename="file.txt",
        media_type="text/plain",
        purpose=FilePurpose.USER_DATA,
    )
    adapter.download_chunks = (b"x" * 1025,)
    with pytest.raises(ControlFileError, match="chunk"):
        async for _ in files.download("openai", "project-a", record.id):
            pass


@pytest.mark.asyncio
async def test_list_uses_stable_cursor_without_skips_or_duplicates(
    tmp_path: Path,
) -> None:
    files, _, _ = service(tmp_path)
    for index in range(5):
        await files.upload(
            "openai",
            chunks(f"file {index}".encode()),
            filename=f"file-{index}.txt",
            media_type="text/plain",
            purpose=FilePurpose.USER_DATA,
        )
    seen: list[str] = []
    cursor = None
    while True:
        page = files.list(
            provider="openai",
            account="project-a",
            after=cursor,
            limit=2,
        )
        seen.extend(item.id for item in page.items)
        cursor = page.next_cursor
        if cursor is None:
            break
    assert seen == [f"file-{index:04d}" for index in range(5)]
    assert len(seen) == len(set(seen))


@pytest.mark.asyncio
async def test_delete_removes_catalog_after_provider_and_audits(tmp_path: Path) -> None:
    files, adapter, control = service(tmp_path)
    record = await files.upload(
        "openai",
        chunks(b"delete me"),
        filename="delete.txt",
        media_type="text/plain",
        purpose=FilePurpose.USER_DATA,
    )
    await files.delete("openai", "project-a", record.id, now=NOW)
    assert adapter.deleted == [record.id]
    with pytest.raises(ControlFileError, match="not found"):
        files.get("openai", "project-a", record.id)
    assert [event.event_type for event in control.audit()] == [
        "control.file.created",
        "control.file.deleted",
    ]
