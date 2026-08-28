"""Security and durability regression tests for the enterprise upload path."""

from __future__ import annotations

from pathlib import Path
from typing import IO, Any

import blake3
import pytest

import app.services.upload_manager as upload_manager_module
from app.core.config import Config
from app.services.upload_manager import UploadManager, UploadSession


class LocalAsyncFile:
    """Small aiofiles-compatible adapter for executor-constrained test runners."""

    def __init__(self, path: Path, mode: str) -> None:
        self._path = path
        self._mode = mode
        self._file: IO[Any] | None = None

    async def __aenter__(self) -> LocalAsyncFile:
        self._file = self._path.open(self._mode)
        return self

    async def __aexit__(self, *_args: object) -> None:
        assert self._file is not None
        self._file.close()

    async def read(self, size: int = -1) -> Any:
        assert self._file is not None
        return self._file.read(size)

    async def write(self, data: Any) -> int:
        assert self._file is not None
        return self._file.write(data)

    async def flush(self) -> None:
        assert self._file is not None
        self._file.flush()


@pytest.fixture(autouse=True)
def local_async_files(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep upload tests deterministic when the host executor is unavailable."""

    monkeypatch.setattr(
        upload_manager_module.aiofiles,
        "open",
        lambda path, mode="r": LocalAsyncFile(Path(path), mode),
    )


class MemoryCache:
    """Minimal cache double matching the upload manager contract."""

    def __init__(self) -> None:
        self.values: dict[str, object] = {}
        self._connected = True

    async def get(self, key: str, default=None):
        return self.values.get(key, default)

    async def set(self, key: str, value, **_kwargs) -> bool:
        self.values[key] = value
        return True

    async def delete(self, key: str) -> bool:
        return self.values.pop(key, None) is not None


def manager(tmp_path: Path) -> UploadManager:
    config = Config(
        environment="test",
        redis_enabled=False,
        nats_enabled=False,
        protobuf_enabled=False,
        upload_temp_dir=tmp_path,
        upload_chunk_size=4,
        upload_max_size=32,
        storage_backend="local",
    )
    instance = UploadManager(config)
    instance.cache = MemoryCache()
    return instance


def test_upload_session_round_trip_preserves_resume_state() -> None:
    session = UploadSession(
        session_id="sess_1",
        tenant_id="tenant-a",
        file_id="file-1",
        file_name="data.bin",
        total_size=8,
        expected_hash="abc",
        chunk_size=4,
        total_chunks=2,
        uploaded_chunks={0},
        chunk_hashes={0: "deadbeef"},
    )

    restored = UploadSession.from_dict(session.to_dict())

    assert restored.tenant_id == "tenant-a"
    assert restored.uploaded_chunks == {0}
    assert restored.chunk_hashes == {0: "deadbeef"}
    assert restored.expected_hash == "abc"


@pytest.mark.asyncio
async def test_session_resumes_from_shared_cache(tmp_path: Path) -> None:
    first = manager(tmp_path)
    session = await first.init_upload(
        tenant_id="tenant-a",
        file_id="file-1",
        file_name="data.bin",
        total_size=4,
    )

    second = manager(tmp_path)
    second.cache = first.cache

    restored = await second.get_session(session.session_id, "tenant-a")
    assert restored is not None
    assert restored.session_id == session.session_id


@pytest.mark.asyncio
async def test_local_session_resumes_after_process_restart(tmp_path: Path) -> None:
    first = manager(tmp_path)
    session = await first.init_upload(
        tenant_id="tenant-a",
        file_id="file-1",
        file_name="data.bin",
        total_size=4,
    )

    second = manager(tmp_path)
    restored = await second.get_session(session.session_id, "tenant-a")

    assert restored is not None
    assert restored.session_id == session.session_id


@pytest.mark.asyncio
async def test_chunk_validation_rejects_negative_index_and_wrong_size(tmp_path: Path) -> None:
    upload = manager(tmp_path)
    session = await upload.init_upload(
        tenant_id="tenant-a",
        file_id="file-1",
        file_name="data.bin",
        total_size=8,
    )
    digest = blake3.blake3(b"abcd").hexdigest()

    with pytest.raises(ValueError, match="non-negative"):
        await upload.upload_chunk(session.session_id, -1, b"abcd", digest, "tenant-a")

    with pytest.raises(ValueError, match="size"):
        await upload.upload_chunk(session.session_id, 0, b"abc", blake3.blake3(b"abc").hexdigest(), "tenant-a")


@pytest.mark.asyncio
async def test_finalize_verifies_full_digest_and_tenant(tmp_path: Path) -> None:
    upload = manager(tmp_path)
    content = b"abcdefgh"
    session = await upload.init_upload(
        tenant_id="tenant-a",
        file_id="file-1",
        file_name="data.bin",
        total_size=len(content),
        expected_hash=blake3.blake3(content).hexdigest(),
    )

    for index, chunk in enumerate((b"abcd", b"efgh")):
        await upload.upload_chunk(
            session.session_id,
            index,
            chunk,
            blake3.blake3(chunk).hexdigest(),
            "tenant-a",
        )

    with pytest.raises(PermissionError):
        await upload.finalize_upload(session.session_id, "tenant-b")

    result = await upload.finalize_upload(session.session_id, "tenant-a")
    assert Path(result).read_bytes() == content
    assert not Path(f"{result}.part").exists()


@pytest.mark.asyncio
async def test_file_id_cannot_escape_storage_root(tmp_path: Path) -> None:
    upload = manager(tmp_path)
    with pytest.raises(ValueError, match="file_id"):
        await upload.init_upload(
            tenant_id="tenant-a",
            file_id="../../escape",
            file_name="data.bin",
            total_size=4,
        )
