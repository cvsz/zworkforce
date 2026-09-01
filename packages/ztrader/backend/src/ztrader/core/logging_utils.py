"""Utilities for writing untrusted values to application logs safely."""

from __future__ import annotations

from typing import Any


def sanitize_log_value(value: Any, max_length: int = 256) -> str:
    """Return a bounded, single-line representation suitable for logs."""
    text = str(value).replace("\r", "\\r").replace("\n", "\\n")
    return text[:max_length]
