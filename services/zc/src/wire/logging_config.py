"""
logging_config.py — Structured logging for production deployments

Provides:
- `setup_logging()`: call once at process start (main.py entrypoint). Reads
  wire_LOG_LEVEL (default INFO) and wire_LOG_FORMAT (`json` or `text`,
  default `text` for interactive TTY use, `json` recommended when running
  under Docker/systemd/a log aggregator).
- A correlation-id contextvar (`correlation_id`) so every log line emitted
  during one CLI invocation (or one request, if this is ever wrapped in a
  service) can be tied together — set once in main.py, read by the
  JSON formatter automatically.
- `RedactingFilter`, which scrubs anything that looks like an API key
  (`sk-ant-...`) or `Authorization`/`x-api-key` header value from every log
  record before it's emitted, so a stray `logger.debug(payload)` can't leak
  a credential into logs/observability pipelines.
"""
from __future__ import annotations

import contextvars
import json
import logging
import os
import re
import sys
import time
import uuid

correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="-")

_SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9\-_]{10,}"),
    re.compile(r"(?i)(x-api-key|authorization)['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9\-_.]{10,}"),
    re.compile(r"(?i)(ANTHROPIC_API_KEY|GITHUB_TOKEN|VOYAGE_API_KEY)['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9\-_.]{6,}"),
]


def redact(text: str) -> str:
    """Scrub known credential shapes out of a string. Best-effort, not a
    substitute for not logging secrets in the first place — see
    security.py for input-side controls."""
    if not text:
        return text
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.msg))
        if record.args:
            record.args = tuple(redact(str(a)) if isinstance(a, str) else a for a in record.args)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id.get(),
        }
        # Extra fields passed via logger.info("event", extra={...})
        for key, value in record.__dict__.items():
            if key in ("args", "msg", "levelname", "levelno", "name", "pathname",
                       "filename", "module", "exc_info", "exc_text", "stack_info",
                       "lineno", "funcName", "created", "msecs", "relativeCreated",
                       "thread", "threadName", "processName", "process", "taskName"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(
            fmt="%(asctime)s [%(levelname)s] [cid=%(correlation_id)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        record.correlation_id = correlation_id.get()
        return super().format(record)


def new_correlation_id() -> str:
    cid = uuid.uuid4().hex[:12]
    correlation_id.set(cid)
    return cid


def setup_logging(level: str | None = None, fmt: str | None = None) -> logging.Logger:
    """Idempotent: safe to call multiple times (e.g. once from main.py and
    once from a test fixture) without duplicating handlers."""
    level = (level or os.getenv("wire_LOG_LEVEL") or "INFO").upper()
    fmt = (fmt or os.getenv("wire_LOG_FORMAT") or ("json" if not sys.stderr.isatty() else "text")).lower()

    root = logging.getLogger("wire")
    root.setLevel(level)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())
    handler.addFilter(RedactingFilter())
    root.addHandler(handler)
    root.propagate = False

    if correlation_id.get() == "-":
        new_correlation_id()

    return root


def get_logger(name: str) -> logging.Logger:
    """Get a child logger under the `wire` namespace, e.g. get_logger('coder')
    -> 'wire.coder'. Falls back to a lazily-configured root if
    setup_logging() hasn't been called yet (e.g. under pytest)."""
    if not logging.getLogger("wire").handlers:
        setup_logging()
    return logging.getLogger(f"wire.{name}")
