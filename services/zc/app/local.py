"""Zero-cost, single-machine runtime profile for the enterprise API."""

from __future__ import annotations

import os
from pathlib import Path

LOCAL_DEFAULTS = {
    "ENVIRONMENT": "development",
    "DEBUG": "true",
    "AUTH_REQUIRED": "false",
    "STORAGE_BACKEND": "local",
    "UPLOAD_TEMP_DIR": "./data/uploads",
    "CHAT_SESSION_DIR": "./data/chat/sessions",
    "REDIS_ENABLED": "false",
    "NATS_ENABLED": "false",
    "OTEL_ENABLED": "false",
    "RATE_LIMIT_ENABLED": "true",
    "CONTROL_PANEL_ENABLED": "true",
    "PROTOBUF_ENABLED": "true",
    "API_HOST": "127.0.0.1",
    "API_PORT": "8000",
    "API_WORKERS": "1",
    "CORS_ORIGINS": "http://127.0.0.1:3000,http://localhost:3000",
}


def apply_local_defaults() -> None:
    """Apply local defaults without overriding explicit user configuration."""
    for name, value in LOCAL_DEFAULTS.items():
        os.environ.setdefault(name, value)
    Path(os.environ["UPLOAD_TEMP_DIR"]).expanduser().resolve().mkdir(
        parents=True, exist_ok=True
    )


def main() -> None:
    """Start HTTP and gRPC services using only local machine resources."""
    apply_local_defaults()
    from .main import run_server

    run_server(workers=1)


__all__ = ["LOCAL_DEFAULTS", "apply_local_defaults", "main"]


if __name__ == "__main__":
    main()
