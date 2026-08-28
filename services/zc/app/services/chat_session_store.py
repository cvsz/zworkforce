"""Atomic tenant-isolated JSON storage for chat sessions."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .resource_store import ResourceConflictError, ResourceNotFoundError

logger = logging.getLogger(__name__)
_SESSION_ID = re.compile(r"\Achat_[0-9a-f]{32}\Z")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AtomicChatSessionStore:
    """Store each session as one atomically replaced local JSON document."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)

    @staticmethod
    def _tenant_namespace(tenant_id: str) -> str:
        return hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()

    def _tenant_dir(self, tenant_id: str) -> Path:
        directory = self.root / self._tenant_namespace(tenant_id)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if directory.is_symlink() or directory.resolve().parent != self.root:
            raise RuntimeError("Invalid chat tenant storage directory")
        os.chmod(directory, 0o700)
        return directory

    def _path(self, tenant_id: str, session_id: str) -> Path:
        if not _SESSION_ID.fullmatch(session_id):
            raise ResourceNotFoundError("chat session not found")
        path = self._tenant_dir(tenant_id) / f"{session_id}.json"
        if path.parent != self._tenant_dir(tenant_id):
            raise ResourceNotFoundError("chat session not found")
        return path

    async def create(
        self,
        tenant_id: str,
        domain: str,
        resource_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        del domain
        return await asyncio.to_thread(
            self._create_sync, tenant_id, resource_id, data
        )

    def _create_sync(
        self,
        tenant_id: str,
        resource_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        path = self._path(tenant_id, resource_id)
        if path.exists():
            raise ResourceConflictError("chat session already exists")
        now = _now()
        document = {
            **data,
            "id": resource_id,
            "created_at": now,
            "updated_at": now,
        }
        self._write_atomic(path, document, replace=False)
        return document

    async def get(
        self, tenant_id: str, domain: str, resource_id: str
    ) -> dict[str, Any]:
        del domain
        return await asyncio.to_thread(self._get_sync, tenant_id, resource_id)

    def _get_sync(self, tenant_id: str, resource_id: str) -> dict[str, Any]:
        path = self._path(tenant_id, resource_id)
        try:
            payload = self._read_json(path)
        except FileNotFoundError as exc:
            raise ResourceNotFoundError("chat session not found") from exc
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.warning("Unreadable chat session %s", resource_id, exc_info=True)
            raise ResourceNotFoundError("chat session not found") from exc
        if not isinstance(payload, dict) or payload.get("id") != resource_id:
            raise ResourceNotFoundError("chat session not found")
        return payload

    async def list(
        self,
        tenant_id: str,
        domain: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        del domain
        return await asyncio.to_thread(
            self._list_sync, tenant_id, limit, offset
        )

    def _list_sync(
        self, tenant_id: str, limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], int]:
        items: list[dict[str, Any]] = []
        for path in self._tenant_dir(tenant_id).glob("chat_*.json"):
            try:
                payload = self._read_json(path)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                logger.warning("Skipping unreadable chat session", exc_info=True)
                continue
            if (
                isinstance(payload, dict)
                and payload.get("id") == path.stem
                and _SESSION_ID.fullmatch(path.stem)
            ):
                items.append(payload)
        items.sort(
            key=lambda item: (str(item.get("updated_at", "")), str(item["id"])),
            reverse=True,
        )
        return items[offset : offset + limit], len(items)

    @staticmethod
    def _read_json(path: Path) -> Any:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            return json.load(handle)

    async def replace(
        self,
        tenant_id: str,
        domain: str,
        resource_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        del domain
        return await asyncio.to_thread(
            self._replace_sync, tenant_id, resource_id, data
        )

    def _replace_sync(
        self,
        tenant_id: str,
        resource_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        path = self._path(tenant_id, resource_id)
        existing = self._get_sync(tenant_id, resource_id)
        document = {
            **data,
            "id": resource_id,
            "created_at": existing["created_at"],
            "updated_at": _now(),
        }
        self._write_atomic(path, document, replace=True)
        return document

    async def delete(
        self, tenant_id: str, domain: str, resource_id: str
    ) -> None:
        del domain
        await asyncio.to_thread(self._delete_sync, tenant_id, resource_id)

    def _delete_sync(self, tenant_id: str, resource_id: str) -> None:
        path = self._path(tenant_id, resource_id)
        try:
            path.unlink()
        except FileNotFoundError as exc:
            raise ResourceNotFoundError("chat session not found") from exc

    @staticmethod
    def _write_atomic(
        path: Path, document: dict[str, Any], *, replace: bool
    ) -> None:
        if not replace and path.exists():
            raise ResourceConflictError("chat session already exists")
        encoded = json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.stem}-",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            if replace:
                os.replace(temporary, path)
            else:
                try:
                    os.link(temporary, path)
                except FileExistsError as exc:
                    raise ResourceConflictError(
                        "chat session already exists"
                    ) from exc
            os.chmod(path, 0o600)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            temporary.unlink(missing_ok=True)


__all__ = ["AtomicChatSessionStore"]
