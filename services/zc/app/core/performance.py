"""
Enterprise Performance Configuration Module
Optimized for 2026 production standards with zero-copy I/O, kernel tuning, and async optimizations.
"""

import asyncio
import mmap
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# =============================================================================
# ZERO-COPY FILE OPERATIONS
# =============================================================================

@dataclass
class ZeroCopyConfig:
    """Configuration for zero-copy file transfers."""
    enabled: bool = True
    chunk_size: int = 4 * 1024 * 1024  # 4MB chunks
    use_sendfile: bool = True
    use_mmap: bool = True
    min_file_size_for_mmap: int = 1024 * 1024  # 1MB


class ZeroCopyFileHandler:
    """High-performance file handler using memory-mapped I/O and sendfile."""

    def __init__(self, config: Optional[ZeroCopyConfig] = None):
        self.config = config or ZeroCopyConfig()

    async def read_file_zero_copy(self, file_path: Path) -> bytes:
        """Read file using memory-mapped I/O for minimal CPU usage."""
        if not self.config.use_mmap:
            return await self._read_file_async(file_path)

        file_size = file_path.stat().st_size

        if file_size < self.config.min_file_size_for_mmap:
            return await self._read_file_async(file_path)

        loop = asyncio.get_event_loop()

        def _mmap_read():
            with open(file_path, 'rb') as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    return mm[:]

        return await loop.run_in_executor(None, _mmap_read)

    async def stream_file_to_socket(self, file_path: Path, sock: socket.socket):
        """Stream file directly to socket using sendfile (zero-copy)."""
        if not self.config.use_sendfile:
            return await self._stream_file_fallback(file_path, sock)

        loop = asyncio.get_event_loop()

        def _sendfile():
            with open(file_path, 'rb') as f:
                os.sendfile(sock.fileno(), f.fileno(), 0, os.path.getsize(file_path))

        await loop.run_in_executor(None, _sendfile)

    async def _read_file_async(self, file_path: Path) -> bytes:
        """Standard async file read fallback."""
        loop = asyncio.get_event_loop()

        def _read():
            with open(file_path, 'rb') as f:
                return f.read()

        return await loop.run_in_executor(None, _read)

    async def _stream_file_fallback(self, file_path: Path, sock: socket.socket):
        """Fallback streaming without sendfile."""
        with open(file_path, 'rb') as f:
            while chunk := f.read(self.config.chunk_size):
                sock.sendall(chunk)


# =============================================================================
# ASYNC LOCK OPTIMIZATION
# =============================================================================

class OptimizedLockManager:
    """Fine-grained locking strategy for high-concurrency scenarios."""

    def __init__(self, max_locks: int = 1000):
        self._locks: dict[str, asyncio.Lock] = {}
        self._max_locks = max_locks
        self._global_lock = asyncio.Lock()

    async def get_lock(self, key: str) -> asyncio.Lock:
        """Get or create a lock for a specific key with LRU eviction."""
        async with self._global_lock:
            if key not in self._locks:
                if len(self._locks) >= self._max_locks:
                    # Evict oldest lock (simple FIFO for now)
                    oldest_key = next(iter(self._locks))
                    del self._locks[oldest_key]
                self._locks[key] = asyncio.Lock()
            return self._locks[key]

    async def acquire(self, key: str):
        """Acquire lock for a specific resource."""
        lock = await self.get_lock(key)
        await lock.acquire()

    def release(self, key: str):
        """Release lock for a specific resource."""
        if key in self._locks:
            try:
                self._locks[key].release()
            except RuntimeError:
                pass  # Lock was not held


# =============================================================================
# MULTITHREADED HASHING
# =============================================================================

class ParallelHasher:
    """BLAKE3 hashing with parallel chunk processing."""

    def __init__(self, num_workers: int = 4, chunk_size: int = 1024 * 1024):
        self.num_workers = num_workers
        self.chunk_size = chunk_size

    async def hash_file_parallel(self, file_path: Path) -> str:
        """Hash file using multiple worker threads."""
        import blake3

        loop = asyncio.get_event_loop()
        file_size = file_path.stat().st_size

        if file_size < self.chunk_size:
            # Small file, single thread is faster
            def _hash_single():
                with open(file_path, 'rb') as f:
                    return blake3.blake3(f.read()).hexdigest()
            return await loop.run_in_executor(None, _hash_single)

        # Large file, parallel hashing
        num_chunks = (file_size + self.chunk_size - 1) // self.chunk_size
        actual_workers = min(self.num_workers, num_chunks)

        def _hash_chunk(args):
            offset, size = args
            with open(file_path, 'rb') as f:
                f.seek(offset)
                data = f.read(size)
                return blake3.blake3(data).digest()

        # Create chunk tasks
        tasks = []
        for i in range(num_chunks):
            offset = i * self.chunk_size
            size = min(self.chunk_size, file_size - offset)
            tasks.append((offset, size))

        # Execute in thread pool
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=actual_workers) as executor:
            chunk_hashes = await loop.run_in_executor(
                executor,
                lambda: list(executor.map(_hash_chunk, tasks))
            )

        # Combine hashes (BLAKE3 tree hashing)
        combined = blake3.blake3(b''.join(chunk_hashes)).hexdigest()
        return combined


# =============================================================================
# REDIS PIPELINE BATCHING
# =============================================================================

class RedisBatchOptimizer:
    """Optimize Redis operations through intelligent batching."""

    def __init__(self, batch_size: int = 100, flush_interval: float = 0.01):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._pending: list = []
        self._lock = asyncio.Lock()

    async def execute_batched(self, redis_client, operation: str, *args):
        """Queue operation for batched execution."""
        async with self._lock:
            self._pending.append((operation, args))

            if len(self._pending) >= self.batch_size:
                await self._flush(redis_client)

    async def _flush(self, redis_client):
        """Execute all pending operations in a pipeline."""
        if not self._pending:
            return

        pipeline = redis_client.pipeline()

        for op, args in self._pending:
            getattr(pipeline, op)(*args)

        await pipeline.execute()
        self._pending.clear()

    async def force_flush(self, redis_client):
        """Force immediate flush of pending operations."""
        async with self._lock:
            await self._flush(redis_client)


# =============================================================================
# UVLOOP INTEGRATION
# =============================================================================

def setup_uvloop():
    """Install uvloop for faster async event loop."""
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        return True
    except ImportError:
        return False


# =============================================================================
# ORJSON SERIALIZATION
# =============================================================================

def get_json_serializer():
    """Get fastest available JSON serializer."""
    try:
        import orjson
        return {
            'dumps': orjson.dumps,
            'loads': orjson.loads,
            'is_binary': True
        }
    except ImportError:
        import ujson
        return {
            'dumps': ujson.dumps,
            'loads': ujson.loads,
            'is_binary': False
        }


# =============================================================================
# SOCKET OPTIONS OPTIMIZATION
# =============================================================================

def optimize_socket(sock: socket.socket):
    """Apply kernel-level socket optimizations."""
    # Enable TCP_NODELAY for low latency
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    # Increase buffer sizes
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)

    # Enable TCP_QUICKACK (Linux only)
    if hasattr(socket, 'TCP_QUICKACK'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)

    # Set SO_KEEPALIVE
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

    # TCP_KEEPIDLE, TCP_KEEPINTVL, TCP_KEEPCNT (Linux only)
    if hasattr(socket, 'TCP_KEEPIDLE'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
    if hasattr(socket, 'TCP_KEEPINTVL'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
    if hasattr(socket, 'TCP_KEEPCNT'):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)


# =============================================================================
# PERFORMANCE METRICS
# =============================================================================

@dataclass
class PerformanceMetrics:
    """Track performance metrics for optimization validation."""
    zero_copy_savings_bytes: int = 0
    parallel_hash_speedup: float = 1.0
    redis_batch_efficiency: float = 1.0
    avg_latency_ms: float = 0.0
    throughput_mbps: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            'zero_copy_savings_bytes': self.zero_copy_savings_bytes,
            'parallel_hash_speedup': self.parallel_hash_speedup,
            'redis_batch_efficiency': self.redis_batch_efficiency,
            'avg_latency_ms': self.avg_latency_ms,
            'throughput_mbps': self.throughput_mbps
        }


# Global instances
_zero_copy_handler: Optional[ZeroCopyFileHandler] = None
_lock_manager: Optional[OptimizedLockManager] = None
_parallel_hasher: Optional[ParallelHasher] = None
_redis_optimizer: Optional[RedisBatchOptimizer] = None


def get_zero_copy_handler() -> ZeroCopyFileHandler:
    global _zero_copy_handler
    if _zero_copy_handler is None:
        _zero_copy_handler = ZeroCopyFileHandler()
    return _zero_copy_handler


def get_lock_manager() -> OptimizedLockManager:
    global _lock_manager
    if _lock_manager is None:
        _lock_manager = OptimizedLockManager()
    return _lock_manager


def get_parallel_hasher() -> ParallelHasher:
    global _parallel_hasher
    if _parallel_hasher is None:
        _parallel_hasher = ParallelHasher()
    return _parallel_hasher


def get_redis_optimizer() -> RedisBatchOptimizer:
    global _redis_optimizer
    if _redis_optimizer is None:
        _redis_optimizer = RedisBatchOptimizer()
    return _redis_optimizer
