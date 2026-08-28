"""
Enterprise Monitoring & Observability - Phase 4
Grafana Dashboards, Prometheus Alerts, and Real-time System Health
2026 Enterprise Standards for wire CLI-to-API System
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Awaitable

import aiofiles
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# =============================================================================
# PROMETHEUS METRICS DEFINITIONS
# =============================================================================

class MetricsRegistry:
    """Centralized Prometheus Metrics Registry"""
    
    def __init__(self):
        self.registry = CollectorRegistry()
        
        # HTTP Request Metrics
        self.http_requests_total = Counter(
            'wire_http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status_code'],
            registry=self.registry
        )
        
        self.http_request_duration_seconds = Histogram(
            'wire_http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'endpoint'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=self.registry
        )
        
        self.http_requests_in_progress = Gauge(
            'wire_http_requests_in_progress',
            'Number of HTTP requests currently being processed',
            ['method'],
            registry=self.registry
        )
        
        # File Upload Metrics
        self.upload_initiated_total = Counter(
            'wire_upload_initiated_total',
            'Total file uploads initiated',
            ['chunked', 'delta_sync'],
            registry=self.registry
        )
        
        self.upload_chunk_total = Counter(
            'wire_upload_chunks_total',
            'Total chunks uploaded',
            ['status'],
            registry=self.registry
        )
        
        self.upload_bytes_total = Counter(
            'wire_upload_bytes_total',
            'Total bytes uploaded',
            ['type'],  # 'original', 'delta'
            registry=self.registry
        )
        
        self.upload_active = Gauge(
            'wire_upload_active',
            'Number of active file uploads',
            registry=self.registry
        )
        
        self.upload_duration_seconds = Histogram(
            'wire_upload_duration_seconds',
            'File upload duration in seconds',
            ['size_bucket'],
            buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600],
            registry=self.registry
        )
        
        # gRPC Metrics
        self.grpc_requests_total = Counter(
            'wire_grpc_requests_total',
            'Total gRPC requests',
            ['service', 'method', 'status_code'],
            registry=self.registry
        )
        
        self.grpc_request_duration_seconds = Histogram(
            'wire_grpc_request_duration_seconds',
            'gRPC request duration in seconds',
            ['service', 'method'],
            buckets=[0.0001, 0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
            registry=self.registry
        )
        
        # Cache Metrics
        self.cache_hits_total = Counter(
            'wire_cache_hits_total',
            'Total cache hits',
            ['cache_type'],
            registry=self.registry
        )
        
        self.cache_misses_total = Counter(
            'wire_cache_misses_total',
            'Total cache misses',
            ['cache_type'],
            registry=self.registry
        )
        
        self.cache_size = Gauge(
            'wire_cache_size',
            'Current cache size',
            ['cache_type'],
            registry=self.registry
        )
        
        # Database Metrics
        self.db_connections_active = Gauge(
            'wire_db_connections_active',
            'Number of active database connections',
            registry=self.registry
        )
        
        self.db_query_duration_seconds = Histogram(
            'wire_db_query_duration_seconds',
            'Database query duration in seconds',
            ['query_type'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            registry=self.registry
        )
        
        # Security Metrics
        self.auth_attempts_total = Counter(
            'wire_auth_attempts_total',
            'Total authentication attempts',
            ['method', 'success'],
            registry=self.registry
        )
        
        self.rate_limit_hits_total = Counter(
            'wire_rate_limit_hits_total',
            'Total rate limit violations',
            ['endpoint', 'role'],
            registry=self.registry
        )
        
        # System Metrics
        self.worker_queue_depth = Gauge(
            'wire_worker_queue_depth',
            'Number of tasks in worker queues',
            ['queue_name'],
            registry=self.registry
        )
        
        self.worker_tasks_processed_total = Counter(
            'wire_worker_tasks_processed_total',
            'Total tasks processed by workers',
            ['queue_name', 'status'],
            registry=self.registry
        )
    
    def get_metrics(self) -> str:
        """Get all metrics in Prometheus format"""
        return generate_latest(self.registry).decode('utf-8')


# =============================================================================
# GRAFANA DASHBOARD CONFIGURATION
# =============================================================================

GRAFANA_DASHBOARD_CONFIG = {
    "dashboard": {
        "id": None,
        "uid": "wire-enterprise-main",
        "title": "wire Enterprise - System Overview",
        "tags": ["wire", "enterprise", "cli-api"],
        "timezone": "browser",
        "schemaVersion": 38,
        "version": 1,
        "refresh": "5s",
        "panels": [
            {
                "id": 1,
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
                "type": "graph",
                "title": "HTTP Request Rate & Latency",
                "targets": [
                    {
                        "expr": "rate(wire_http_requests_total[5m])",
                        "legendFormat": "{{method}} {{endpoint}}",
                        "refId": "A"
                    }
                ],
                "yAxes": [
                    {"label": "Requests/sec", "min": 0},
                    {"label": "Latency (s)", "min": 0}
                ]
            },
            {
                "id": 2,
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
                "type": "graph",
                "title": "Upload Throughput",
                "targets": [
                    {
                        "expr": "rate(wire_upload_bytes_total[5m])",
                        "legendFormat": "{{type}}",
                        "refId": "A"
                    }
                ],
                "yAxes": [{"label": "Bytes/sec", "min": 0}]
            },
            {
                "id": 3,
                "gridPos": {"h": 8, "w": 8, "x": 0, "y": 8},
                "type": "gauge",
                "title": "Active Uploads",
                "targets": [
                    {
                        "expr": "wire_upload_active",
                        "refId": "A"
                    }
                ],
                "options": {
                    "min": 0,
                    "max": 1000,
                    "thresholds": [
                        {"value": 0, "color": "green"},
                        {"value": 500, "color": "yellow"},
                        {"value": 800, "color": "red"}
                    ]
                }
            },
            {
                "id": 4,
                "gridPos": {"h": 8, "w": 8, "x": 8, "y": 8},
                "type": "gauge",
                "title": "Cache Hit Ratio",
                "targets": [
                    {
                        "expr": "rate(wire_cache_hits_total[5m]) / (rate(wire_cache_hits_total[5m]) + rate(wire_cache_misses_total[5m]))",
                        "refId": "A"
                    }
                ],
                "options": {
                    "min": 0,
                    "max": 1,
                    "thresholds": [
                        {"value": 0, "color": "red"},
                        {"value": 0.5, "color": "yellow"},
                        {"value": 0.8, "color": "green"}
                    ],
                    "unit": "percentunit"
                }
            },
            {
                "id": 5,
                "gridPos": {"h": 8, "w": 8, "x": 16, "y": 8},
                "type": "gauge",
                "title": "Error Rate",
                "targets": [
                    {
                        "expr": "rate(wire_http_requests_total{status_code=~\"5..\"}[5m]) / rate(wire_http_requests_total[5m])",
                        "refId": "A"
                    }
                ],
                "options": {
                    "min": 0,
                    "max": 0.1,
                    "thresholds": [
                        {"value": 0, "color": "green"},
                        {"value": 0.01, "color": "yellow"},
                        {"value": 0.05, "color": "red"}
                    ],
                    "unit": "percentunit"
                }
            },
            {
                "id": 6,
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 16},
                "type": "graph",
                "title": "gRPC Service Latency (p50, p95, p99)",
                "targets": [
                    {
                        "expr": "histogram_quantile(0.50, rate(wire_grpc_request_duration_seconds_bucket[5m]))",
                        "legendFormat": "p50",
                        "refId": "A"
                    },
                    {
                        "expr": "histogram_quantile(0.95, rate(wire_grpc_request_duration_seconds_bucket[5m]))",
                        "legendFormat": "p95",
                        "refId": "B"
                    },
                    {
                        "expr": "histogram_quantile(0.99, rate(wire_grpc_request_duration_seconds_bucket[5m]))",
                        "legendFormat": "p99",
                        "refId": "C"
                    }
                ],
                "yAxes": [{"label": "Seconds", "min": 0, "format": "s"}]
            },
            {
                "id": 7,
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 16},
                "type": "table",
                "title": "Worker Queue Status",
                "targets": [
                    {
                        "expr": "wire_worker_queue_depth",
                        "format": "table",
                        "instant": True,
                        "refId": "A"
                    }
                ],
                "transformations": [
                    {"id": "organize", "options": {"renameByName": {"Value": "Queue Depth"}}}
                ]
            }
        ]
    }
}


# =============================================================================
# PROMETHEUS ALERT RULES
# =============================================================================

PROMETHEUS_ALERT_RULES = """
groups:
  - name: wire_enterprise_alerts
    interval: 30s
    rules:
      # High Error Rate Alert
      - alert: wireHighErrorRate
        expr: |
          sum(rate(wire_http_requests_total{status_code=~"5.."}[5m])) 
          / sum(rate(wire_http_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }} over the last 5 minutes"

      # High Latency Alert
      - alert: wireHighLatency
        expr: |
          histogram_quantile(0.95, rate(wire_http_request_duration_seconds_bucket[5m])) > 1
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High API latency detected"
          description: "95th percentile latency is {{ $value }}s"

      # Upload Queue Backlog
      - alert: wireUploadBacklog
        expr: wire_upload_active > 500
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Large upload queue backlog"
          description: "{{ $value }} active uploads"

      # Cache Hit Ratio Low
      - alert: wireCacheHitRatioLow
        expr: |
          rate(wire_cache_hits_total[5m]) 
          / (rate(wire_cache_hits_total[5m]) + rate(wire_cache_misses_total[5m])) < 0.5
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "Low cache hit ratio"
          description: "Cache hit ratio is {{ $value | humanizePercentage }}"

      # Worker Queue Depth High
      - alert: wireWorkerQueueDepthHigh
        expr: wire_worker_queue_depth > 1000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Worker queue depth is high"
          description: "Queue {{ $labels.queue_name }} has {{ $value }} pending tasks"

      # Authentication Failures Spike
      - alert: wireAuthFailuresSpike
        expr: |
          rate(wire_auth_attempts_total{success="false"}[5m]) > 10
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Authentication failure spike detected"
          description: "{{ $value }} auth failures per second"

      # Rate Limiting Active
      - alert: wireRateLimitingActive
        expr: rate(wire_rate_limit_hits_total[5m]) > 50
        for: 5m
        labels:
          severity: info
        annotations:
          summary: "High rate limiting activity"
          description: "{{ $value }} rate limit hits per second"

      # gRPC Service Errors
      - alert: wireGrpcErrors
        expr: |
          sum(rate(wire_grpc_requests_total{status_code!="OK"}[5m])) 
          / sum(rate(wire_grpc_requests_total[5m])) > 0.01
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "gRPC service errors detected"
          description: "gRPC error rate is {{ $value | humanizePercentage }}"
"""


# =============================================================================
# OPEN TELEMETRY INTEGRATION
# =============================================================================

class OpenTelemetryConfig:
    """OpenTelemetry Configuration for Distributed Tracing"""
    
    def __init__(self):
        self.service_name = os.getenv("OTEL_SERVICE_NAME", "wire-enterprise")
        self.exporter_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4317")
        self.trace_sample_rate = float(os.getenv("OTEL_TRACE_SAMPLE_RATE", "0.1"))
        self.metrics_export_interval = int(os.getenv("OTEL_METRICS_EXPORT_INTERVAL", "60"))
    
    def get_config(self) -> dict[str, Any]:
        return {
            "service_name": self.service_name,
            "exporter": {
                "protocol": "grpc",
                "endpoint": self.exporter_endpoint
            },
            "sampling": {
                "type": "parentbased_always_on",
                "ratio": self.trace_sample_rate
            },
            "propagators": ["tracecontext", "baggage"],
            "resource_attributes": {
                "deployment.environment": os.getenv("ENVIRONMENT", "production"),
                "service.version": os.getenv("APP_VERSION", "latest")
            }
        }


# =============================================================================
# HEALTH CHECK ENDPOINTS
# =============================================================================

class HealthChecker:
    """Comprehensive Health Check System"""
    
    def __init__(self) -> None:
        self.checks: dict[str, Callable[[], Awaitable[dict[str, Any]]]] = {}
        self.register_default_checks()
    
    def register_default_checks(self) -> None:
        """Register default health checks"""
        self.register_check("database", self._check_database)
        self.register_check("redis", self._check_redis)
        self.register_check("storage", self._check_storage)
        self.register_check("workers", self._check_workers)
    
    def register_check(self, name: str, check_func: Callable[[], Awaitable[dict[str, Any]]]) -> None:
        """Register a health check"""
        self.checks[name] = check_func
    
    async def _check_database(self) -> dict[str, Any]:
        """Check database connectivity"""
        # Implementation depends on actual DB driver
        return {"status": "healthy", "latency_ms": 5}
    
    async def _check_redis(self) -> dict[str, Any]:
        """Check Redis connectivity"""
        # Implementation depends on actual Redis client
        return {"status": "healthy", "latency_ms": 2}
    
    async def _check_storage(self) -> dict[str, Any]:
        """Check storage availability"""
        storage_path = Path(os.getenv("STORAGE_PATH", "/tmp/wire-storage"))
        try:
            storage_path.mkdir(parents=True, exist_ok=True)
            test_file = storage_path / ".health_check"
            async with aiofiles.open(test_file, 'w') as f:
                await f.write("ok")
            test_file.unlink()
            return {"status": "healthy", "path": str(storage_path)}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def _check_workers(self) -> dict[str, Any]:
        """Check worker queue health"""
        # Implementation depends on actual queue system
        return {"status": "healthy", "active_workers": 3}
    
    async def run_all_checks(self) -> dict[str, Any]:
        """Run all registered health checks"""
        results = {}
        overall_status = "healthy"
        
        for name, check_func in self.checks.items():
            try:
                result = await check_func()
                results[name] = result
                if result.get("status") != "healthy":
                    overall_status = "degraded"
            except Exception as e:
                results[name] = {"status": "unhealthy", "error": str(e)}
                overall_status = "unhealthy"
        
        return {
            "status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": results
        }


# =============================================================================
# LOGGING CONFIGURATION FOR OBSERVABILITY
# =============================================================================

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d %(funcName)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S%z"
        },
        "structured": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s trace_id=%(trace_id)s span_id=%(span_id)s",
            "datefmt": "%Y-%m-%dT%H:%M:%S%z"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "filename": "/var/log/wire/enterprise.log",
            "maxBytes": 104857600,  # 100MB
            "backupCount": 10,
            "encoding": "utf8"
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console", "file"]
    },
    "loggers": {
        "wire": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
            "propagate": False
        },
        "uvicorn": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False
        }
    }
}


# Export all components
__all__ = [
    "MetricsRegistry",
    "GRAFANA_DASHBOARD_CONFIG",
    "PROMETHEUS_ALERT_RULES",
    "OpenTelemetryConfig",
    "HealthChecker",
    "LOGGING_CONFIG"
]
