from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
import time
from typing import Any, Callable
import urllib.parse
import urllib.request
import uuid


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    start_time_unix_nano: int = 0
    end_time_unix_nano: int = 0
    attributes: dict[str, Any] = field(default_factory=dict)
    status_code: int = 1  # 1: OK, 2: ERROR
    status_message: str = ""


class OtlpHttpExporter:
    """Production-grade OTLP/HTTP JSON Trace Exporter supporting OpenTelemetry Collector,
    Langfuse, Grafana Cloud, and Arize AX sinks.
    """
    def __init__(self, endpoint: str, headers: dict[str, str] | None = None, timeout: float = 5.0, service_name: str = "zworkforce"):
        self.endpoint = str(endpoint or "").strip()
        self.headers = dict(headers or {})
        self.timeout = max(1.0, float(timeout))
        self.service_name = str(service_name or "zworkforce").strip()
        if self.endpoint:
            p = urllib.parse.urlsplit(self.endpoint)
            if p.scheme not in {"http", "https"} or not p.hostname:
                raise ValueError("invalid OTLP traces endpoint")
            if p.scheme != "https" and p.hostname not in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError("remote OTLP traces endpoint must use HTTPS")

    def export(self, name: str, started_ns: int, ended_ns: int, attributes: dict | None = None, status: str = "OK", trace_id: str | None = None, parent_span_id: str | None = None) -> str:
        if not self.endpoint:
            return ""
        tid = trace_id or uuid.uuid4().hex
        sid = uuid.uuid4().hex[:16]
        
        # Scrub attributes of any accidental secrets / sensitive keys
        safe_attributes = {}
        for k, v in (attributes or {}).items():
            k_str = str(k).lower()
            if any(s in k_str for s in ("secret", "token", "password", "api_key", "key_ref")):
                safe_attributes[str(k)] = "[REDACTED]"
            else:
                safe_attributes[str(k)] = str(v)

        span_obj: dict[str, Any] = {
            "traceId": tid,
            "spanId": sid,
            "name": name,
            "kind": 1,
            "startTimeUnixNano": str(started_ns),
            "endTimeUnixNano": str(ended_ns),
            "attributes": [{"key": str(k), "value": {"stringValue": str(v)}} for k, v in safe_attributes.items()],
            "status": {"code": 1 if status == "OK" else 2},
        }
        if parent_span_id:
            span_obj["parentSpanId"] = str(parent_span_id)

        body = {
            "resourceSpans": [{
                "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": self.service_name}}]},
                "scopeSpans": [{
                    "scope": {"name": "zworkforce", "version": "3.0.4"},
                    "spans": [span_obj]
                }],
            }]
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json", **self.headers}
        req = urllib.request.Request(self.endpoint, data=json.dumps(body, separators=(",", ":")).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp.read(1024)
        except Exception:
            # Telemetry must never disrupt task execution.
            pass
        return sid


class _TelemetryProvider:
    def __init__(self, provider, exporter: OtlpHttpExporter):
        self._provider = provider
        self._exporter = exporter

    def __getattr__(self, name):
        return getattr(self._provider, name)

    def chat(self, tier: str, messages: list[dict], tools: list[dict], tenant_id: str | None = None):
        start = time.time_ns()
        status = "OK"
        attrs = {"tier": str(tier), "num_messages": len(messages), "num_tools": len(tools)}
        try:
            result = self._provider.chat(tier, messages, tools, tenant_id=tenant_id)
            if hasattr(result, "usage") and result.usage:
                attrs["input_tokens"] = getattr(result.usage, "input_tokens", 0)
                attrs["cached_tokens"] = getattr(result.usage, "cached_tokens", 0)
                attrs["output_tokens"] = getattr(result.usage, "output_tokens", 0)
            if hasattr(result, "provider_name"):
                attrs["provider_name"] = str(result.provider_name)
            if hasattr(result, "model"):
                attrs["model"] = str(result.model)
            return result
        except Exception as exc:
            status = "ERROR"
            attrs["error_type"] = exc.__class__.__name__
            raise
        finally:
            self._exporter.export("provider.chat", start, time.time_ns(), attrs, status)


def wrap_provider_from_env(provider):
    endpoint = os.getenv("ZWORKFORCE_OTLP_TRACES_ENDPOINT", "").strip()
    if not endpoint:
        return provider
    headers: dict[str, str] = {}
    raw = os.getenv("ZWORKFORCE_OTLP_HEADERS_JSON", "").strip()
    if raw:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("ZWORKFORCE_OTLP_HEADERS_JSON must be an object")
        headers = {str(k): str(v) for k, v in parsed.items()}
    service_name = os.getenv("ZWORKFORCE_SERVICE_NAME", "zworkforce").strip() or "zworkforce"
    return _TelemetryProvider(provider, OtlpHttpExporter(endpoint, headers, service_name=service_name))
