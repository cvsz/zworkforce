#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import ssl
import time
import urllib.request
from pathlib import Path


def fetch(url: str, timeout: float) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "zworkforce-cme-verifier/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="cme.zeaz.dev")
    parser.add_argument("--expected-release", required=True)
    parser.add_argument("--release-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args()

    release = Path(args.release_file).read_text(encoding="utf-8").strip()
    if release != args.expected_release:
        raise SystemExit("deployed release identity mismatch")

    addresses = sorted({item[4][0] for item in socket.getaddrinfo(args.host, 443, type=socket.SOCK_STREAM)})
    context = ssl.create_default_context()
    with socket.create_connection((args.host, 443), timeout=args.timeout) as sock:
        with context.wrap_socket(sock, server_hostname=args.host) as tls:
            certificate = tls.getpeercert()
            cipher = tls.cipher()
            tls_version = tls.version()

    health_status, health_body = fetch(f"https://{args.host}/health", args.timeout)
    ready_status, ready_body = fetch(f"https://{args.host}/ready", args.timeout)
    if health_status != 200 or '"status":"ok"' not in health_body.replace(" ", ""):
        raise SystemExit("health verification failed")
    if ready_status != 200 or '"status":"ready"' not in ready_body.replace(" ", ""):
        raise SystemExit("readiness verification failed")

    evidence = {
        "schema": "zeaz.cme.production-verification/v1",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": args.host,
        "dns_addresses": addresses,
        "tls_version": tls_version,
        "tls_cipher": cipher[0] if cipher else None,
        "certificate_subject": certificate.get("subject"),
        "certificate_not_after": certificate.get("notAfter"),
        "expected_release": args.expected_release,
        "observed_release": release,
        "health_status": health_status,
        "readiness_status": ready_status,
        "result": "PASS",
    }
    Path(args.output).write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
