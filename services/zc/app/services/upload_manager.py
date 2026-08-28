"""
app/services/upload_manager.py - Enterprise file upload service

Features:
- Chunked uploads with configurable chunk sizes (default 4MB)
- Resumable uploads via session tracking
- Delta updates using BLAKE3 content hashing
- Content-addressable storage for deduplication
- Async processing pipeline integration
- Real-time progress tracking via Redis

Architecture:
1. Client initiates upload with file metadata
2. Server returns missing chunk indices (delta detection)
3. Client uploads chunks in parallel
4. Server validates and stores each chunk
5. Finalization assembles complete file
"""
import asyncio
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import aiofiles
import blake3

from ..core.cache import CacheKey, get_cache
from ..core.config import Config, get_config


@dataclass
class UploadSession:
    """Represents an active upload session."""
    session_id: str
    tenant_id: str
    file_id: str
    file_name: str
    total_size: int
    expected_hash: Optional[str]
    chunk_size: int
    total_chunks: int
    uploaded_chunks: set[int] = field(default_factory=set)
    chunk_hashes: dict[int, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 3600)
    status: str = "pending"  # pending, uploading, completed, failed
    error_message: Optional[str] = None

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def progress_percent(self) -> float:
        if self.total_chunks == 0:
            return 100.0
        return (len(self.uploaded_chunks) / self.total_chunks) * 100

    def missing_chunks(self) -> list[int]:
        return [i for i in range(self.total_chunks) if i not in self.uploaded_chunks]

    def to_dict(self) -> dict[str, Any]:
        return {
            'session_id': self.session_id,
            'tenant_id': self.tenant_id,
            'file_id': self.file_id,
            'file_name': self.file_name,
            'total_size': self.total_size,
            'expected_hash': self.expected_hash,
            'chunk_size': self.chunk_size,
            'total_chunks': self.total_chunks,
            'uploaded_chunks': sorted(self.uploaded_chunks),
            'chunk_hashes': {str(key): value for key, value in self.chunk_hashes.items()},
            'uploaded_count': len(self.uploaded_chunks),
            'missing_chunks': self.missing_chunks(),
            'progress_percent': self.progress_percent(),
            'status': self.status,
            'created_at': self.created_at,
            'expires_at': self.expires_at,
            'error_message': self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UploadSession":
        """Reconstruct a durable upload session from shared cache state."""
        return cls(
            session_id=str(data["session_id"]),
            tenant_id=str(data["tenant_id"]),
            file_id=str(data["file_id"]),
            file_name=str(data["file_name"]),
            total_size=int(data["total_size"]),
            expected_hash=data.get("expected_hash"),
            chunk_size=int(data["chunk_size"]),
            total_chunks=int(data["total_chunks"]),
            uploaded_chunks={int(value) for value in data.get("uploaded_chunks", [])},
            chunk_hashes={
                int(key): str(value)
                for key, value in data.get("chunk_hashes", {}).items()
            },
            created_at=float(data.get("created_at", time.time())),
            expires_at=float(data.get("expires_at", time.time() + 3600)),
            status=str(data.get("status", "pending")),
            error_message=data.get("error_message"),
        )


class UploadManager:
    """
    Enterprise-grade file upload manager with chunking and resumability.
    
    Usage:
        manager = UploadManager()
        await manager.init()
        
        # Initialize upload
        session = await manager.init_upload(
            file_id="doc123",
            file_name="large_file.bin",
            total_size=1073741824,  # 1GB
            client_chunk_hashes={0: "hash1", 1: "hash2"}  # For delta
        )
        
        # Upload chunks
        await manager.upload_chunk(
            session_id=session.session_id,
            chunk_index=2,
            data=chunk_bytes,
            chunk_hash=computed_hash
        )
        
        # Finalize
        await manager.finalize_upload(session.session_id)
    """

    _SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.cache = get_cache()

        # In-memory session store (synced with Redis)
        self._sessions: dict[str, UploadSession] = {}
        self._lock = asyncio.Lock()

        # Storage paths
        self.chunks_dir = self.config.upload_temp_dir / "chunks"
        self.files_dir = self.config.upload_temp_dir / "files"
        self.sessions_dir = self.config.upload_temp_dir / "sessions"
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    async def init(self) -> None:
        """Initialize the upload manager."""
        # Ensure cache is connected
        if not self.cache._connected:
            await self.cache.connect()

        # Recover any incomplete sessions from Redis
        await self._recover_sessions()

    async def _recover_sessions(self) -> None:
        """Recover incomplete upload sessions from Redis."""
        for session_path in self.sessions_dir.glob("sess_*.json"):
            try:
                async with aiofiles.open(session_path, "r") as session_file:
                    session = UploadSession.from_dict(json.loads(await session_file.read()))
                if not session.is_expired():
                    self._sessions[session.session_id] = session
                else:
                    session_path.unlink(missing_ok=True)
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                continue
        if not self.cache._connected or self.cache.redis_client is None:
            return
        pattern = CacheKey.build("upload", "session", "*")
        cursor = 0
        while True:
            cursor, keys = await self.cache.redis_client.scan(
                cursor, match=pattern, count=100
            )
            for raw_key in keys:
                key = raw_key.decode() if isinstance(raw_key, bytes) else str(raw_key)
                cached = await self.cache.get(key)
                if cached:
                    session = UploadSession.from_dict(cached)
                    if not session.is_expired():
                        self._sessions[session.session_id] = session
            if cursor == 0:
                break

    async def init_upload(
        self,
        file_id: str,
        file_name: str,
        total_size: int,
        tenant_id: str = "default",
        expected_hash: Optional[str] = None,
        client_chunk_hashes: Optional[dict[int, str]] = None,
        chunk_size: Optional[int] = None,
    ) -> UploadSession:
        """
        Initialize a new upload session.
        
        Args:
            file_id: Unique identifier for the file
            file_name: Original filename
            total_size: Total file size in bytes
            client_chunk_hashes: Map of chunk_index -> hash for delta detection
            chunk_size: Override default chunk size
            
        Returns:
            UploadSession with missing chunk indices
        """
        if not self._SAFE_ID.fullmatch(file_id):
            raise ValueError("file_id must be a safe opaque identifier")
        if not self._SAFE_ID.fullmatch(tenant_id):
            raise ValueError("tenant_id must be a safe opaque identifier")
        if total_size <= 0 or total_size > self.config.upload_max_size:
            raise ValueError(
                f"total_size must be between 1 and {self.config.upload_max_size}"
            )
        chunk_size = chunk_size or self.config.upload_chunk_size
        if chunk_size <= 0 or chunk_size > self.config.max_message_size:
            raise ValueError("chunk_size is outside the configured limit")
        if expected_hash and not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            raise ValueError("expected_hash must be a lowercase BLAKE3 digest")
        total_chunks = (total_size + chunk_size - 1) // chunk_size

        session_id = f"sess_{file_id}_{hashlib.blake2b(os.urandom(16)).hexdigest()[:16]}"

        session = UploadSession(
            session_id=session_id,
            tenant_id=tenant_id,
            file_id=file_id,
            file_name=file_name,
            total_size=total_size,
            expected_hash=expected_hash,
            chunk_size=chunk_size,
            total_chunks=total_chunks,
        )

        # Detect existing chunks for delta upload
        if client_chunk_hashes:
            for idx, client_hash in client_chunk_hashes.items():
                if 0 <= idx < total_chunks:
                    # Check if we already have this chunk
                    chunk_path = self.chunks_dir / tenant_id / client_hash
                    if chunk_path.exists():
                        session.uploaded_chunks.add(idx)
                        session.chunk_hashes[idx] = client_hash

        # Store session
        async with self._lock:
            self._sessions[session_id] = session

        # Cache session metadata
        cache_key = CacheKey.build('upload', 'session', session_id)
        await self.cache.set(cache_key, session.to_dict(), ttl=3600)

        # Track in Redis for distributed systems
        redis_key = CacheKey.build('upload', 'active', session_id)
        await self.cache.set(redis_key, {
            'file_id': file_id,
            'status': 'pending',
            'created_at': time.time(),
        }, ttl=3600)
        await self._persist_session(session)

        return session

    async def upload_chunk(
        self,
        session_id: str,
        chunk_index: int,
        data: bytes,
        chunk_hash: str,
        tenant_id: str = "default",
    ) -> bool:
        """
        Upload a single chunk.
        
        Args:
            session_id: Upload session ID
            chunk_index: Zero-based chunk index
            data: Raw chunk bytes
            chunk_hash: BLAKE3 hash of the chunk
            
        Returns:
            True if successfully stored
        """
        # Validate session
        session = await self.get_session(session_id, tenant_id)
        if not session:
            raise ValueError(f"Invalid or expired session: {session_id}")

        if session.is_expired():
            raise ValueError(f"Session expired: {session_id}")

        if chunk_index < 0:
            raise ValueError("Chunk index must be non-negative")
        if chunk_index >= session.total_chunks:
            raise ValueError(f"Chunk index {chunk_index} exceeds total {session.total_chunks}")

        expected_size = session.chunk_size
        if chunk_index == session.total_chunks - 1:
            expected_size = session.total_size - (chunk_index * session.chunk_size)
        if len(data) != expected_size:
            raise ValueError(
                f"Chunk size mismatch: expected {expected_size}, got {len(data)}"
            )

        # Verify hash
        computed_hash = blake3.blake3(data).hexdigest()
        if computed_hash != chunk_hash:
            raise ValueError(
                f"Hash mismatch: expected {chunk_hash}, got {computed_hash}"
            )

        # Store chunk (content-addressable)
        tenant_chunk_dir = self.chunks_dir / session.tenant_id
        tenant_chunk_dir.mkdir(parents=True, exist_ok=True)
        chunk_path = tenant_chunk_dir / chunk_hash
        if not chunk_path.exists():
            temporary_path = chunk_path.with_name(
                f".{chunk_path.name}.{os.getpid()}.{chunk_index}.part"
            )
            async with aiofiles.open(temporary_path, 'wb') as f:
                await f.write(data)
                await f.flush()
            try:
                os.link(temporary_path, chunk_path)
            except FileExistsError:
                pass
            finally:
                temporary_path.unlink(missing_ok=True)

        # Update session
        async with self._lock:
            session.uploaded_chunks.add(chunk_index)
            session.chunk_hashes[chunk_index] = chunk_hash
            session.status = 'uploading'

        # Update cache
        cache_key = CacheKey.build('upload', 'session', session_id)
        await self.cache.set(cache_key, session.to_dict(), ttl=3600)

        # Update progress in Redis for real-time monitoring
        progress_key = CacheKey.build('upload', 'progress', session_id)
        await self.cache.set(progress_key, {
            'uploaded': len(session.uploaded_chunks),
            'total': session.total_chunks,
            'percent': session.progress_percent(),
        }, ttl=3600)

        # Check if complete
        if len(session.uploaded_chunks) == session.total_chunks:
            session.status = 'completed'
            await self.cache.set(cache_key, session.to_dict(), ttl=3600)
        await self._persist_session(session)

        return True

    async def finalize_upload(
        self, session_id: str, tenant_id: str = "default"
    ) -> str:
        """
        Finalize an upload by assembling all chunks.
        
        Args:
            session_id: Upload session ID
            
        Returns:
            Path to the assembled file
        """
        session = await self.get_session(session_id, tenant_id)
        if not session:
            raise ValueError(f"Invalid session: {session_id}")

        if session.status != 'completed':
            raise ValueError(
                f"Upload not complete: {session.status} "
                f"({len(session.uploaded_chunks)}/{session.total_chunks})"
            )

        # Assemble file
        tenant_files_dir = self.files_dir / session.tenant_id
        tenant_files_dir.mkdir(parents=True, exist_ok=True)
        output_path = tenant_files_dir / session.file_id
        temporary_path = output_path.with_suffix(".part")
        full_digest = blake3.blake3()
        bytes_written = 0
        try:
            async with aiofiles.open(temporary_path, 'wb') as output:
                for idx in range(session.total_chunks):
                    chunk_hash = session.chunk_hashes.get(idx)
                    if not chunk_hash:
                        raise ValueError(f"Missing chunk {idx}")

                    chunk_path = self.chunks_dir / session.tenant_id / chunk_hash
                    async with aiofiles.open(chunk_path, 'rb') as chunk_file:
                        while block := await chunk_file.read(1024 * 1024):
                            full_digest.update(block)
                            bytes_written += len(block)
                            await output.write(block)
                await output.flush()

            if bytes_written != session.total_size:
                raise ValueError(
                    f"Final size mismatch: expected {session.total_size}, got {bytes_written}"
                )
            computed_hash = full_digest.hexdigest()
            if session.expected_hash and computed_hash != session.expected_hash:
                raise ValueError(
                    f"Final hash mismatch: expected {session.expected_hash}, got {computed_hash}"
                )
            os.replace(temporary_path, output_path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

        # Update session
        async with self._lock:
            session.status = 'finalized'

        # Cleanup: remove individual chunks after TTL
        # (In production, schedule background cleanup)

        await self.cache.set(
            CacheKey.build("upload", "session", session_id),
            session.to_dict(),
            ttl=3600,
        )
        await self._persist_session(session)
        return str(output_path)

    async def cancel_upload(
        self, session_id: str, tenant_id: str = "default"
    ) -> bool:
        """Cancel an upload session."""
        session = await self.get_session(session_id, tenant_id)
        if not session:
            return False
        async with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                session.status = 'cancelled'
                del self._sessions[session_id]

        # Remove from cache
        cache_key = CacheKey.build('upload', 'session', session_id)
        await self.cache.delete(cache_key)
        self._session_path(session_id).unlink(missing_ok=True)

        return True

    async def get_progress(
        self, session_id: str, tenant_id: str = "default"
    ) -> dict[str, Any]:
        """Get upload progress."""
        session = await self.get_session(session_id, tenant_id)
        if not session:
            return {'error': 'Session not found'}

        return session.to_dict()

    async def list_sessions(self, tenant_id: str) -> list[dict[str, Any]]:
        """List locally known tenant sessions without exposing other tenants."""
        async with self._lock:
            return [
                session.to_dict()
                for session in self._sessions.values()
                if session.tenant_id == tenant_id and not session.is_expired()
            ]

    async def get_session(
        self, session_id: str, tenant_id: str = "default"
    ) -> Optional[UploadSession]:
        """Get and authorize a session from memory or shared cache."""
        async with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                if not session.is_expired():
                    if session.tenant_id != tenant_id:
                        raise PermissionError("Upload session belongs to another tenant")
                    return session
                else:
                    del self._sessions[session_id]

        # Try cache
        cache_key = CacheKey.build('upload', 'session', session_id)
        cached = await self.cache.get(cache_key)
        if cached:
            session = UploadSession.from_dict(cached)
            if session.is_expired():
                await self.cache.delete(cache_key)
                return None
            if session.tenant_id != tenant_id:
                raise PermissionError("Upload session belongs to another tenant")
            async with self._lock:
                self._sessions[session_id] = session
            return session

        session_path = self._session_path(session_id)
        if session_path.exists():
            try:
                async with aiofiles.open(session_path, "r") as session_file:
                    session = UploadSession.from_dict(
                        json.loads(await session_file.read())
                    )
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                return None
            if session.is_expired():
                session_path.unlink(missing_ok=True)
                return None
            if session.tenant_id != tenant_id:
                raise PermissionError("Upload session belongs to another tenant")
            async with self._lock:
                self._sessions[session_id] = session
            return session

        return None

    def _session_path(self, session_id: str) -> Any:
        """Return a safe local metadata path for a generated session ID."""
        if not session_id.startswith("sess_") or not self._SAFE_ID.fullmatch(session_id):
            raise ValueError("Invalid upload session identifier")
        return self.sessions_dir / f"{session_id}.json"

    async def _persist_session(self, session: UploadSession) -> None:
        """Atomically persist resumable metadata for dependency-free local mode."""
        session_path = self._session_path(session.session_id)
        temporary_path = session_path.with_suffix(
            f".{os.getpid()}.part"
        )
        async with aiofiles.open(temporary_path, "w") as session_file:
            await session_file.write(json.dumps(session.to_dict(), separators=(",", ":")))
            await session_file.flush()
        os.replace(temporary_path, session_path)

    async def _get_session(self, session_id: str) -> Optional[UploadSession]:
        """Backward-compatible internal lookup for the default tenant."""
        return await self.get_session(session_id, "default")

    async def health_check(self) -> dict[str, Any]:
        """Check upload manager health."""
        async with self._lock:
            active_sessions = len([
                s for s in self._sessions.values()
                if not s.is_expired() and s.status in ('pending', 'uploading')
            ])

        # Check disk space
        try:
            stat = os.statvfs(self.config.upload_temp_dir)
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
        except Exception:
            free_gb = 0

        return {
            'active_sessions': active_sessions,
            'temp_dir': str(self.config.upload_temp_dir),
            'free_disk_gb': round(free_gb, 2),
            'cache_connected': self.cache._connected,
        }


# Global instance
_upload_manager: Optional[UploadManager] = None


def get_upload_manager() -> UploadManager:
    """Get or create the global upload manager."""
    global _upload_manager
    if _upload_manager is None:
        _upload_manager = UploadManager()
    return _upload_manager


async def init_upload_manager() -> UploadManager:
    """Initialize the global upload manager."""
    global _upload_manager
    _upload_manager = UploadManager()
    await _upload_manager.init()
    return _upload_manager
