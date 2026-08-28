# Telemetry Package for wire API
"""OpenTelemetry integration for distributed tracing and metrics."""

from .otel_service import TelemetryService, get_telemetry, init_telemetry

__all__ = [
    "TelemetryService",
    "get_telemetry",
    "init_telemetry"
]
