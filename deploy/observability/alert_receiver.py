#!/usr/bin/env python3
"""Private Alertmanager receipt endpoint for release evidence.

The endpoint deliberately stores only receipt metadata. Alertmanager payloads
can contain operator or service annotations, so retaining the complete body is
not necessary for the release verifier and would increase the data exposure
surface.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import tempfile
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit


MAX_BODY_BYTES = 1024 * 1024
TOKEN_RE = re.compile(r"^[A-Za-z0-9._~-]{32,256}$")
EVIDENCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def load_token(path: Path) -> str:
    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError("unable to read receiver token file") from exc
    if not TOKEN_RE.fullmatch(token):
        raise RuntimeError("receiver token file contains an invalid token")
    return token


def evidence_key(evidence_id: str) -> str:
    return hashlib.sha256(evidence_id.encode("utf-8")).hexdigest()


def valid_evidence_id(value: Any) -> bool:
    return isinstance(value, str) and bool(EVIDENCE_ID_RE.fullmatch(value))


class ReceiptHTTPServer(HTTPServer):
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], token: str, data_dir: Path):
        super().__init__(address, ReceiptRequestHandler)
        self.token = token
        self.data_dir = data_dir
        self._write_lock = threading.Lock()

    def authorized(self, header: str | None) -> bool:
        scheme, separator, presented = (header or "").partition(" ")
        return (
            separator == " "
            and scheme.lower() == "bearer"
            and hmac.compare_digest(presented, self.token)
        )

    def receipt_path(self, evidence_id: str) -> Path:
        return self.data_dir / f"{evidence_key(evidence_id)}.json"

    def save_receipt(self, record: dict[str, Any]) -> None:
        target = self.receipt_path(record["evidence_id"])
        with self._write_lock:
            temporary: str | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=self.data_dir,
                    prefix=".receipt-",
                    suffix=".tmp",
                    delete=False,
                ) as stream:
                    temporary = stream.name
                    json.dump(record, stream, sort_keys=True, separators=(",", ":"))
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(temporary, 0o600)
                os.replace(temporary, target)
                temporary = None
                try:
                    directory_fd = os.open(self.data_dir, os.O_RDONLY | os.O_DIRECTORY)
                except OSError:
                    directory_fd = None
                if directory_fd is not None:
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
            finally:
                if temporary is not None:
                    try:
                        os.unlink(temporary)
                    except FileNotFoundError:
                        pass


class ReceiptRequestHandler(BaseHTTPRequestHandler):
    server: ReceiptHTTPServer
    server_version = "zWorkforceAlertReceipt/1"
    sys_version = ""

    # The request path may contain operator credentials in misconfigured
    # clients. Keep access logs disabled so credentials cannot enter journald.
    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def unauthorized(self) -> None:
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", "Bearer")
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlsplit(self.path)
        if parsed.path == "/healthz":
            self.send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if parsed.path != "/receipt":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        if not self.server.authorized(self.headers.get("Authorization")):
            self.unauthorized()
            return
        values = parse_qs(parsed.query, keep_blank_values=True).get("evidence_id", [])
        if len(values) != 1 or not valid_evidence_id(values[0]):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid evidence_id"})
            return
        evidence_id = values[0]
        try:
            record = json.loads(self.server.receipt_path(evidence_id).read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "receipt not found"})
            return
        except (OSError, json.JSONDecodeError):
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "receipt unavailable"})
            return
        if not isinstance(record, dict) or record.get("evidence_id") != evidence_id:
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "receipt unavailable"})
            return
        self.send_json(HTTPStatus.OK, record)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        if urlsplit(self.path).path != "/ingest":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        if not self.server.authorized(self.headers.get("Authorization")):
            self.unauthorized()
            return
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("application/json"):
            self.send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "application/json required"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            content_length = -1
        if content_length < 0:
            self.send_json(HTTPStatus.LENGTH_REQUIRED, {"error": "content length required"})
            return
        if content_length > MAX_BODY_BYTES:
            self.send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "request too large"})
            return
        raw = self.rfile.read(content_length)
        if len(raw) != content_length:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "incomplete request"})
            return
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON"})
            return
        if not isinstance(payload, dict) or not isinstance(payload.get("alerts"), list):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid Alertmanager payload"})
            return

        evidence_ids: set[str] = set()
        for alert in payload["alerts"]:
            if isinstance(alert, dict) and isinstance(alert.get("labels"), dict):
                value = alert["labels"].get("evidence_id")
                if valid_evidence_id(value):
                    evidence_ids.add(value)
        common_labels = payload.get("commonLabels")
        if isinstance(common_labels, dict):
            value = common_labels.get("evidence_id")
            if valid_evidence_id(value):
                evidence_ids.add(value)

        received_at = utc_now()
        payload_hash = hashlib.sha256(raw).hexdigest()
        for evidence_id in sorted(evidence_ids):
            self.server.save_receipt(
                {
                    "evidence_id": evidence_id,
                    "received_at": received_at,
                    "alert_count": len(payload["alerts"]),
                    "payload_sha256": payload_hash,
                }
            )
        self.send_json(
            HTTPStatus.ACCEPTED,
            {"accepted": True, "receipt_count": len(evidence_ids)},
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default=os.getenv("ALERT_RECEIVER_BIND", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("ALERT_RECEIVER_PORT", "18080")))
    parser.add_argument(
        "--token-file",
        type=Path,
        default=Path(os.getenv("ALERT_RECEIVER_TOKEN_FILE", "/opt/zworkforce-observability/alert-receiver-token")),
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.getenv("ALERT_RECEIVER_DATA_DIR", "/opt/zworkforce-observability/alert-receipts")),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.port <= 65535:
        raise SystemExit("receiver port is outside the valid range")
    token = load_token(args.token_file)
    args.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(args.data_dir, 0o700)
    server = ReceiptHTTPServer((args.bind, args.port), token, args.data_dir)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
