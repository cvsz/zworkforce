import asyncio
import logging
from typing import Callable, Any
from functools import wraps

logger = logging.getLogger(__name__)

class CircuitBreakerOpenException(Exception):
    pass

class CircuitBreaker:
    """A simple per-service circuit breaker."""
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = "CLOSED" # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time: float = 0.0

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        import time
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenException("Circuit is OPEN")

        try:
            result = await func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                self.last_failure_time = time.time()
                logger.error("Circuit breaker tripped to OPEN state")
            raise e

def circuit_breaker(threshold: int = 5, timeout: int = 30):
    breaker = CircuitBreaker(threshold, timeout)
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator

class RateLimitExceeded(Exception):
    pass

class RateLimiter:
    """Distributed token bucket rate limiter using Redis."""
    def __init__(self, redis_client: Any, capacity: int, refill_rate: float):
        self.redis = redis_client
        self.capacity = capacity
        self.refill_rate = refill_rate # tokens per second
    
    async def acquire(self, key: str, tokens: int = 1) -> bool:
        if not self.redis:
            return True # Fallback if no redis
        
        import time
        now = time.time()
        
        # Simple lua script for token bucket
        lua_script = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local requested = tonumber(ARGV[3])
        local now = tonumber(ARGV[4])
        
        local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = bucket[1]
        local last_refill = bucket[2]
        
        if not tokens or not last_refill then
            tokens = capacity
            last_refill = now
        else
            tokens = tonumber(tokens)
            last_refill = tonumber(last_refill)
        end
        
        local elapsed = math.max(0, now - last_refill)
        tokens = math.min(capacity, tokens + (elapsed * refill_rate))
        
        if tokens >= requested then
            tokens = tokens - requested
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
            redis.call('EXPIRE', key, math.ceil(capacity / refill_rate) + 10)
            return 1
        else
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
            return 0
        end
        """
        
        result = await self.redis.eval(lua_script, 1, key, self.capacity, self.refill_rate, tokens, now)
        if not result:
            raise RateLimitExceeded("Rate limit exceeded")
        return True

class BulkheadExhausted(Exception):
    pass

class Bulkhead:
    """Resource isolation using connection limits / semaphore."""
    def __init__(self, max_concurrent: int):
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        
    async def __aenter__(self):
        # We use a zero timeout trick to fail fast if locked
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=0.1)
        except asyncio.TimeoutError:
            raise BulkheadExhausted("Bulkhead capacity exhausted")
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._semaphore.release()
