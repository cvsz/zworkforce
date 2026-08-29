"""
Real-time Latency Profiler Middleware for Enterprise wire API
Tracks p50, p95, p99 latencies with automatic alerting on regressions.
"""

import asyncio
import logging
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


@dataclass
class LatencyMetrics:
    """Track latency percentiles and trends."""
    samples: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    @property
    def count(self) -> int:
        return len(self.samples)
    
    @property
    def p50(self) -> float:
        if not self.samples:
            return 0.0
        return statistics.median(self.samples)
    
    @property
    def p95(self) -> float:
        if not self.samples:
            return 0.0
        sorted_samples = sorted(self.samples)
        idx = int(len(sorted_samples) * 0.95)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]
    
    @property
    def p99(self) -> float:
        if not self.samples:
            return 0.0
        sorted_samples = sorted(self.samples)
        idx = int(len(sorted_samples) * 0.99)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]
    
    @property
    def avg(self) -> float:
        if not self.samples:
            return 0.0
        return statistics.mean(self.samples)
    
    def add_sample(self, latency_ms: float):
        self.samples.append(latency_ms)
    
    def to_dict(self) -> dict:
        return {
            'count': self.count,
            'p50_ms': round(self.p50, 3),
            'p95_ms': round(self.p95, 3),
            'p99_ms': round(self.p99, 3),
            'avg_ms': round(self.avg, 3)
        }


class LatencyProfiler:
    """Centralized latency tracking across all endpoints."""
    
    def __init__(self, alert_threshold_p99: float = 100.0):
        self._metrics: dict[str, LatencyMetrics] = {}
        self._alert_threshold_p99 = alert_threshold_p99
        self._global_metrics = LatencyMetrics()
        self._alerts: list[dict] = []
    
    def get_metrics(self, endpoint: str) -> LatencyMetrics:
        if endpoint not in self._metrics:
            self._metrics[endpoint] = LatencyMetrics()
        return self._metrics[endpoint]
    
    def record(self, endpoint: str, latency_ms: float):
        """Record a latency sample for an endpoint."""
        self._global_metrics.add_sample(latency_ms)
        endpoint_metrics = self.get_metrics(endpoint)
        endpoint_metrics.add_sample(latency_ms)
        
        # Check for regression alerts
        if latency_ms > self._alert_threshold_p99:
            self._create_alert(endpoint, latency_ms)
    
    def _create_alert(self, endpoint: str, latency_ms: float):
        """Create an alert for high latency."""
        alert = {
            'timestamp': time.time(),
            'endpoint': endpoint,
            'latency_ms': latency_ms,
            'threshold': self._alert_threshold_p99,
            'severity': 'critical' if latency_ms > self._alert_threshold_p99 * 2 else 'warning'
        }
        self._alerts.append(alert)
        logger.warning(f"HIGH_LATENCY: {endpoint} took {latency_ms:.2f}ms (threshold: {self._alert_threshold_p99}ms)")
    
    def get_global_metrics(self) -> dict:
        return self._global_metrics.to_dict()
    
    def get_all_endpoint_metrics(self) -> dict[str, dict]:
        return {ep: m.to_dict() for ep, m in self._metrics.items()}
    
    def get_recent_alerts(self, limit: int = 10) -> list[dict]:
        return self._alerts[-limit:]
    
    def reset_alerts(self):
        self._alerts.clear()


# Global profiler instance
_profiler: Optional[LatencyProfiler] = None


def get_profiler() -> LatencyProfiler:
    global _profiler
    if _profiler is None:
        _profiler = LatencyProfiler(alert_threshold_p99=100.0)
    return _profiler


class LatencyProfilerMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware to profile request latencies in real-time."""
    
    def __init__(self, app, profiler: Optional[LatencyProfiler] = None):
        super().__init__(app)
        self.profiler = profiler or get_profiler()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        
        # Execute request
        response = await call_next(request)
        
        # Calculate latency
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        
        # Record metrics
        endpoint = f"{request.method}:{request.url.path}"
        self.profiler.record(endpoint, latency_ms)
        
        # Add latency header to response
        response.headers['X-Response-Time-Ms'] = f"{latency_ms:.3f}"
        response.headers['X-Latency-P99'] = f"{self.profiler.get_metrics(endpoint).p99:.3f}"
        
        return response


# =============================================================================
# ASYNC DECORATOR FOR SPECIFIC ENDPOINTS
# =============================================================================

def profile_latency(endpoint_name: Optional[str] = None):
    """Decorator to profile latency of specific async functions."""
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            name = endpoint_name or func.__name__
            profiler = get_profiler()
            
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000
                profiler.record(name, latency_ms)
        
        return wrapper
    return decorator


# =============================================================================
# PERIODIC METRICS EXPORTER
# =============================================================================

async def export_metrics_periodically(interval_seconds: int = 60):
    """Periodically log latency metrics for monitoring."""
    while True:
        await asyncio.sleep(interval_seconds)
        
        profiler = get_profiler()
        global_metrics = profiler.get_global_metrics()
        
        logger.info(
            f"LATENCY_REPORT: "
            f"p50={global_metrics['p50_ms']:.2f}ms, "
            f"p95={global_metrics['p95_ms']:.2f}ms, "
            f"p99={global_metrics['p99_ms']:.2f}ms, "
            f"samples={global_metrics['count']}"
        )
        
        # Log top 5 slowest endpoints
        all_metrics = profiler.get_all_endpoint_metrics()
        sorted_endpoints = sorted(
            all_metrics.items(),
            key=lambda x: x[1]['p99_ms'],
            reverse=True
        )[:5]
        
        if sorted_endpoints:
            logger.info("TOP_5_SLOWEST_ENDPOINTS:")
            for ep, metrics in sorted_endpoints:
                logger.info(f"  {ep}: p99={metrics['p99_ms']:.2f}ms")
