#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def write_evidence(path: Path, evidence: dict[str, object]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(evidence, handle, indent=2)
        handle.write("\n")


def fetch_json(url: str, timeout: float, host: str) -> tuple[int, dict[str, object]]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != host or parsed.port not in (None, 443):
        raise RuntimeError("verification URL must use the expected CMe HTTPS host")
    headers = {"User-Agent": "zworkforce-cme-verifier/1"}
    access_id = os.environ.get("ZWORKFORCE_ACCESS_ID")
    access_token = os.environ.get("ZWORKFORCE_ACCESS_TOKEN")
    if not access_id or not access_token:
        raise RuntimeError("machine Access credentials are required")
    headers["CF-Access-Client-Id"] = access_id
    headers["CF-Access-Client-Secret"] = access_token
    opener = urllib.request.build_opener(NoRedirect)
    request = urllib.request.Request(url, headers=headers)
    with opener.open(request, timeout=timeout) as response:
        final = urlparse(response.geturl())
        requested = urlparse(url)
        if final.scheme != "https" or final.hostname != requested.hostname:
            raise RuntimeError("endpoint redirected away from requested HTTPS host")
        payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("endpoint did not return a JSON object")
        return response.status, payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="cme.zeaz.dev")
    parser.add_argument("--expected-release", required=True)
    parser.add_argument("--runtime-release-url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--approval-reference", required=True)
    parser.add_argument("--terraform-plan-reference", required=True)
    parser.add_argument("--terraform-apply-reference", required=True)
    parser.add_argument("--deployment-reference", required=True)
    parser.add_argument("--alert-receipt", required=True)
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args()

    output = Path(args.output)
    evidence_refs = {
        "operator": args.operator,
        "approval_reference": args.approval_reference,
        "terraform_plan_reference": args.terraform_plan_reference,
        "terraform_apply_reference": args.terraform_apply_reference,
        "deployment_reference": args.deployment_reference,
        "alert_receipt": args.alert_receipt,
    }
    if any(not value.strip() for value in evidence_refs.values()):
        parser.error("production evidence references must be non-empty")
    evidence: dict[str, object] = {
        "schema": "zeaz.cme.production-verification/v1",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": args.host,
        "expected_release": args.expected_release,
        "runtime_release_url": args.runtime_release_url,
        "result": "FAIL",
        **evidence_refs,
    }
    try:
        addresses = sorted({item[4][0] for item in socket.getaddrinfo(args.host, 443, type=socket.SOCK_STREAM)})
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        with socket.create_connection((args.host, 443), timeout=args.timeout) as sock:
            with context.wrap_socket(sock, server_hostname=args.host) as tls:
                certificate = tls.getpeercert()
                cipher = tls.cipher()
                evidence.update({
                    "dns_addresses": addresses,
                    "tls_version": tls.version(),
                    "tls_cipher": cipher[0] if cipher else None,
                    "certificate_subject": certificate.get("subject"),
                    "certificate_not_after": certificate.get("notAfter"),
                })

        release_status, release_payload = fetch_json(args.runtime_release_url, args.timeout, args.host)
        observed_release = release_payload.get("release")
        if release_status != 200 or observed_release != args.expected_release:
            raise RuntimeError("runtime release identity mismatch")

        health_status, health = fetch_json(f"https://{args.host}/health", args.timeout, args.host)
        ready_status, ready = fetch_json(f"https://{args.host}/ready", args.timeout, args.host)
        if health_status != 200 or health.get("status") != "ok":
            raise RuntimeError("health verification failed")
        if ready_status != 200 or ready.get("status") != "ready":
            raise RuntimeError("readiness verification failed")

        evidence.update({
            "observed_release": observed_release,
            "health_status": health_status,
            "readiness_status": ready_status,
            "result": "PASS",
        })
        write_evidence(output, evidence)
        print(json.dumps(evidence))
        return 0
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        write_evidence(output, evidence)
        print(json.dumps(evidence))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
