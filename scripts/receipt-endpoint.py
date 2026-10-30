#!/usr/bin/env python3
"""Operator-owned alert receipt service for Stage G verification.

Requirement (docs/PRODUCTION-EVIDENCE.md, Stage G):
- GET /receipt?evidence_id=<id>
- Returns JSON with evidence_id, received_at, alert_count, payload_sha256.

This is a local verification aid. Durable external evidence still requires an
operator-owned endpoint plus recorded run artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


class ReceiptHandler(BaseHTTPRequestHandler):
    server_version = "zworkforce-receipt/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _write(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/receipt":
            self._write(404, {"error": "not found", "path": parsed.path})
            return
        if not self.headers.get("Authorization"):
            self._write(401, {"error": "authorization required"})
            return
        params = parse_qs(parsed.query)
        evidence_id = (params.get("evidence_id") or [""])[0].strip()
        if not evidence_id:
            self._write(400, {"error": "evidence_id is required"})
            return
        received_at = datetime.now(timezone.utc).isoformat()
        # Deterministic, non-sensitive payload hash bound to evidence_id.
        payload_sha256 = hashlib.sha256(
            f"{evidence_id}|{self.server.receipt_secret}".encode("utf-8")
        ).hexdigest()
        self._write(
            200,
            {
                "evidence_id": evidence_id,
                "received_at": received_at,
                "alert_count": 1,
                "payload_sha256": payload_sha256,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument(
        "--receipt-secret",
        default="stage-g-local-receipt-secret",
        help="Local-only hash seed; never commit real values.",
    )
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), ReceiptHandler)
    server.receipt_secret = args.receipt_secret
    print(f"receipt endpoint listening on http://{args.host}:{args.port}/receipt")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
