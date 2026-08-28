"""
Rate Limiter & Circuit Breaker Middleware
Enterprise-grade traffic control with token bucket and circuit breaker patterns.
"""

import time
import json
from collections import defaultdict
from typing import Any, Callable, Optional

from fastapi import HTTPException, Request, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.cache import get_cache


class TokenBucket:
    """Token bucket rate limiter implementation."""

    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity  # Max tokens
        self.refill_rate = refill_rate  # Tokens per second
        self.tokens: float = float(capacity)
        self.last_refill = time.time()

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if successful."""
        now = time.time()
        elapsed = now - self.last_refill

        # Refill tokens based on elapsed time
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    async def consume_async(self, tokens: int = 1) -> bool:
        """Async version using Redis for distributed rate limiting."""
        cache = get_cache()
        if not cache._connected or not cache.redis_client:
            return True
        redis = cache.redis_client
        key = f"ratelimit:{int(time.time()) // 60}"  # Per-minute buckets

        current = await redis.get(key)
        current_count = int(current) if current else 0

        if current_count < self.capacity:
            pipe = redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, 60)
            await pipe.execute()
            return True
        return False


class CircuitBreaker:
    """Circuit breaker pattern for fault tolerance."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state = self.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0

    def record_success(self):
        """Record a successful call."""
        self.failure_count = 0
        if self.state == self.HALF_OPEN:
            self.state = self.CLOSED
        self.half_open_calls = 0

    def record_failure(self):
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == self.HALF_OPEN:
            self.state = self.OPEN
        elif self.failure_count >= self.failure_threshold:
            self.state = self.OPEN

    def can_execute(self) -> bool:
        """Check if a call can be executed."""
        if self.state == self.CLOSED:
            return True

        if self.state == self.OPEN:
            if self.last_failure_time is not None and (time.time() - self.last_failure_time) > self.recovery_timeout:
                self.state = self.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False

        if self.state == self.HALF_OPEN:
            if self.half_open_calls < self.half_open_max_calls:
                self.half_open_calls += 1
                return True
            return False

        return False

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if not self.can_execute():
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable (circuit open)"
            )

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise


class RateLimitMiddleware:
    """FastAPI middleware for rate limiting."""

    EXEMPT_PATHS = frozenset({"/", "/ready", "/v1/wire/health/live"})

    def __init__(
        self, app: ASGIApp, requests_per_minute: int = 100, burst: int = 20
    ) -> None:
        self.app = app
        self.bucket = TokenBucket(capacity=burst, refill_rate=requests_per_minute / 60.0)
        self.client_buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(capacity=burst, refill_rate=requests_per_minute / 60.0)
        )

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http" or scope["path"] in self.EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        client_ip = request.client.host if request.client else "unknown"
        allowed = True
        remaining = 0

        # Redis is authoritative in multi-replica deployments. The in-process
        # bucket is only a development fallback.
        from ..core.cache import get_cache
        from ..core.config import get_config

        cache = get_cache()
        config = get_config()
        if cache._connected and cache.redis_client is not None:
            window = int(time.time() // 60)
            key = f"rtl:http:{client_ip}:{window}"
            count = int(await cache.redis_client.incr(key))
            if count == 1:
                await cache.redis_client.expire(key, 61)
            allowed = count <= self.bucket.capacity
            remaining = max(0, int(self.bucket.capacity) - count)
        elif config.environment == "production" and config.redis_enabled:
            response = Response(
                status_code=503,
                content=json.dumps({"error": "rate_limiter_unavailable"}),
                media_type="application/json",
            )
            await response(scope, receive, send)
            return
        else:
            bucket = self.client_buckets[client_ip]
            allowed = bucket.consume()
            remaining = int(bucket.tokens)

        if not allowed:
            response = Response(
                status_code=429,
                content=json.dumps({
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests. Please slow down.",
                    "retry_after": 60
                }),
                media_type="application/json"
            )
            await response(scope, receive, send)
            return

        async def send_with_rate_limit_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-ratelimit-limit", str(self.bucket.capacity).encode()),
                        (b"x-ratelimit-remaining", str(remaining).encode()),
                        (b"x-ratelimit-reset", str(int(time.time()) + 60).encode()),
                    ]
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_rate_limit_headers)


# Global circuit breakers for different services
circuit_breakers: dict[str, CircuitBreaker] = {
    "database": CircuitBreaker(failure_threshold=5, recovery_timeout=30.0),
    "redis": CircuitBreaker(failure_threshold=3, recovery_timeout=10.0),
    "external_api": CircuitBreaker(failure_threshold=5, recovery_timeout=60.0),
    "file_storage": CircuitBreaker(failure_threshold=5, recovery_timeout=30.0),
}


async def safe_redis_operation(operation_name: str, func: Callable, *args, **kwargs) -> Any:
    """Execute Redis operation with circuit breaker protection."""
    cb = circuit_breakers.get("redis")
    if cb:
        return await cb.execute(func, *args, **kwargs)
    return await func(*args, **kwargs)


async def safe_database_operation(operation_name: str, func: Callable, *args, **kwargs) -> Any:
    """Execute database operation with circuit breaker protection."""
    cb = circuit_breakers.get("database")
    if cb:
        return await cb.execute(func, *args, **kwargs)
    return await func(*args, **kwargs)
