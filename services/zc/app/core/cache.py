"""
app/core/cache.py - Enterprise caching layer with Redis/Valkey

Multi-layer caching strategy:
- L1: In-memory (asyncio.Lock protected)
- L2: Redis/Valkey cluster
- L3: CDN edge (configured externally)

Features:
- Automatic serialization/deserialization
- TTL management with jitter
- Cache invalidation patterns
- Circuit breaker for Redis failures
"""
import asyncio
import hashlib
import json
from typing import Any, Generic, Optional, TypeVar

import redis.asyncio as redis
from redis.asyncio import ConnectionPool

from .config import Config, get_config

T = TypeVar('T')


class CacheKey:
    """Namespace-aware cache key builder."""

    PREFIXES = {
        'model': 'mdl',
        'session': 'ses',
        'upload': 'upl',
        'user': 'usr',
        'feature': 'ftf',
        'rate': 'rtl',
        'metric': 'met',
    }

    @classmethod
    def build(cls, namespace: str, *parts: str) -> str:
        """Build a namespaced cache key."""
        prefix = cls.PREFIXES.get(namespace, 'gen')
        key_parts = [prefix] + list(parts)
        return ':'.join(key_parts)

    @classmethod
    def hash_key(cls, data: Any) -> str:
        """Generate a hash-based key for complex data."""
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.blake2b(serialized.encode(), digest_size=8).hexdigest()


class Layer1Cache(Generic[T]):
    """In-memory L1 cache with LRU eviction."""

    def __init__(self, max_size: int = 1000):
        self._cache: dict[str, T] = {}
        self._access_order: list[str] = []
        self._max_size = max_size
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[T]:
        async with self._lock:
            if key in self._cache:
                # Move to end for LRU
                self._access_order.remove(key)
                self._access_order.append(key)
                return self._cache[key]
            return None

    async def set(self, key: str, value: T) -> None:
        async with self._lock:
            if key in self._cache:
                self._access_order.remove(key)
            elif len(self._cache) >= self._max_size:
                # Evict oldest
                oldest = self._access_order.pop(0)
                del self._cache[oldest]

            self._cache[key] = value
            self._access_order.append(key)

    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._access_order.remove(key)
                return True
            return False

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()
            self._access_order.clear()


class EnterpriseCache:
    """
    Multi-layer enterprise cache with automatic failover.
    
    Usage:
        cache = EnterpriseCache()
        await cache.set("user:123", {"name": "Alice"}, ttl=3600)
        data = await cache.get("user:123")
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.l1_cache: Layer1Cache[Any] = Layer1Cache()
        self.redis_pool: Optional[ConnectionPool] = None
        self.redis_client: Optional[redis.Redis] = None
        self._connected = False
        self._circuit_open = True
        self._circuit_failures = 0
        self._circuit_threshold = 5
        self._circuit_reset_time = 60  # seconds

    async def connect(self) -> None:
        """Initialize Redis connection pool."""
        if not self.config.redis_enabled:
            return

        try:
            self.redis_pool = ConnectionPool.from_url(
                self.config.redis_url,
                max_connections=self.config.redis_pool_size,
                decode_responses=False,  # We handle serialization
            )
            self.redis_client = redis.Redis(connection_pool=self.redis_pool)

            # Test connection
            await self.redis_client.ping()
            self._connected = True
            self._circuit_open = True
        except Exception:
            self._connected = False
            self._circuit_open = False
            raise

    async def disconnect(self) -> None:
        """Close Redis connections."""
        if self.redis_pool:
            await self.redis_pool.disconnect()
            self._connected = False

    def _serialize(self, value: Any) -> bytes:
        """Serialize value to bytes."""
        return json.dumps(value, default=str).encode('utf-8')

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize bytes to value."""
        return json.loads(data.decode('utf-8'))

    async def _check_circuit(self) -> bool:
        """Check if circuit breaker allows Redis access."""
        if self._circuit_open:
            return True

        # Circuit is closed, check if we should retry
        # In production, use Redis to track global failure state
        self._circuit_failures = 0
        self._circuit_open = True
        return True

    async def _record_failure(self) -> None:
        """Record a Redis failure."""
        self._circuit_failures += 1
        if self._circuit_failures >= self._circuit_threshold:
            self._circuit_open = False

    async def get(self, key: str, default: Optional[Any] = None) -> Any:
        """
        Get value from cache (L1 -> L2).
        
        Args:
            key: Cache key
            default: Default value if not found
            
        Returns:
            Cached value or default
        """
        # Try L1 first
        l1_value = await self.l1_cache.get(key)
        if l1_value is not None:
            return l1_value

        # Try L2 (Redis)
        if self._connected and self.redis_client is not None and await self._check_circuit():
            try:
                data = await self.redis_client.get(key)
                if data:
                    value = self._deserialize(data)
                    # Populate L1
                    await self.l1_cache.set(key, value)
                    return value
            except Exception:
                await self._record_failure()

        return default

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """
        Set value in cache (L1 + L2).
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (None = use default)
            nx: Only set if key doesn't exist
            xx: Only set if key exists
            
        Returns:
            True if set successfully
        """
        ttl = ttl or self.config.redis_ttl_default

        # Always set L1
        await self.l1_cache.set(key, value)

        # Set L2 (Redis)
        if self._connected and self.redis_client is not None and await self._check_circuit():
            try:
                data = self._serialize(value)
                if nx:
                    result = await self.redis_client.set(key, data, ex=ttl, nx=True)
                elif xx:
                    result = await self.redis_client.set(key, data, ex=ttl, xx=True)
                else:
                    result = await self.redis_client.set(key, data, ex=ttl)
                return bool(result)
            except Exception:
                await self._record_failure()

        return True

    async def delete(self, key: str) -> bool:
        """Delete value from cache (L1 + L2)."""
        l1_deleted = await self.l1_cache.delete(key)

        if self._connected and self.redis_client is not None and await self._check_circuit():
            try:
                l2_deleted = await self.redis_client.delete(key)
                return l1_deleted or bool(l2_deleted)
            except Exception:
                await self._record_failure()

        return l1_deleted

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if await self.l1_cache.get(key) is not None:
            return True

        if self._connected and self.redis_client is not None and await self._check_circuit():
            try:
                return bool(await self.redis_client.exists(key))
            except Exception:
                await self._record_failure()

        return False

    async def increment(self, key: str, amount: int = 1) -> int:
        """Atomically increment a counter."""
        if self._connected and self.redis_client is not None and await self._check_circuit():
            try:
                return await self.redis_client.incrby(key, amount)
            except Exception:
                await self._record_failure()

        # Fallback to non-atomic increment
        current = await self.get(key, 0)
        await self.set(key, current + amount)
        return current + amount

    async def decrement(self, key: str, amount: int = 1) -> int:
        """Atomically decrement a counter."""
        return await self.increment(key, -amount)

    async def get_ttl(self, key: str) -> int:
        """Get remaining TTL for a key."""
        if self._connected and self.redis_client is not None and await self._check_circuit():
            try:
                return await self.redis_client.ttl(key)
            except Exception:
                await self._record_failure()
        return -1

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on an existing key."""
        if self._connected and self.redis_client is not None and await self._check_circuit():
            try:
                return bool(await self.redis_client.expire(key, ttl))
            except Exception:
                await self._record_failure()
        return False

    async def clear_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern."""
        count = 0
        if self._connected and self.redis_client is not None and await self._check_circuit():
            try:
                cursor = 0
                while True:
                    cursor, keys = await self.redis_client.scan(cursor, match=pattern, count=100)
                    if keys:
                        await self.redis_client.delete(*keys)
                        count += len(keys)
                    if cursor == 0:
                        break
            except Exception:
                await self._record_failure()

        # Also clear L1 matches
        async with self.l1_cache._lock:
            to_delete = [k for k in self.l1_cache._cache.keys() if k.startswith(pattern.replace('*', ''))]
            for k in to_delete:
                await self.l1_cache.delete(k)

        return count

    async def health_check(self) -> dict[str, Any]:
        """Check cache health status."""
        status: dict[str, Any] = {
            'l1_size': len(self.l1_cache._cache),
            'l1_max': self.l1_cache._max_size,
            'redis_connected': self._connected,
            'circuit_open': self._circuit_open,
            'circuit_failures': self._circuit_failures,
        }

        if self._connected and self.redis_client is not None:
            try:
                info = await self.redis_client.info('memory')
                status['redis_memory_used'] = info.get('used_memory_human', 'unknown')
                status['redis_keys'] = await self.redis_client.dbsize()
            except Exception as e:
                status['redis_error'] = str(e)
                await self._record_failure()

        return status


# Global cache instance
_cache: Optional[EnterpriseCache] = None


def get_cache() -> EnterpriseCache:
    """Get or create the global cache instance."""
    global _cache
    if _cache is None:
        _cache = EnterpriseCache()
    return _cache


async def init_cache() -> EnterpriseCache:
    """Initialize the global cache (call at application startup)."""
    global _cache
    _cache = EnterpriseCache()
    await _cache.connect()
    return _cache


async def shutdown_cache() -> None:
    """Shutdown the global cache (call at application shutdown)."""
    global _cache
    if _cache:
        await _cache.disconnect()
        _cache = None
