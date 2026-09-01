from __future__ import annotations

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any

from ztrader.abt.binance_perp_bot.runtime import BotRuntimeState
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


class HealthServer:
    """Small stdlib HTTP server for Docker, Prometheus, and SSH-tunnel probes."""

    def __init__(self, state: BotRuntimeState, host: str, port: int) -> None:
        self.state = state
        self.host = host
        self.port = port
        self.logger = logging.getLogger(__name__)
        self._server = ThreadingHTTPServer((host, port), self._handler())
        self._thread = Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> None:
        self._thread.start()
        self.logger.info(
            "health_server_started",
            extra={"trace_id": "health", "symbol": "system", "strategy": "health"},
        )

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        state = self.state

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
                if self.path == "/health":
                    status = (
                        HTTPStatus.OK
                        if state.live
                        else HTTPStatus.SERVICE_UNAVAILABLE
                    )
                    self._write_json(status, state.as_dict())
                    return
                if self.path == "/ready":
                    status = (
                        HTTPStatus.OK
                        if state.ready
                        else HTTPStatus.SERVICE_UNAVAILABLE
                    )
                    self._write_json(status, state.as_dict())
                    return
                if self.path == "/metrics":
                    payload = generate_latest()
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", CONTENT_TYPE_LATEST)
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

            def log_message(self, format: str, *args: Any) -> None:
                return

            def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
                encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        return Handler
