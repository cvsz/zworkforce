#!/usr/bin/env python3
"""Read-only, authenticated zwslcore provider and zWorkforce MCP interoperability probe.

Never reads .env files, prints tokens, configures routes, or executes tools.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

MAX_RESPONSE = 131072
PRIVATE_NETWORKS = tuple(ipaddress.ip_network(c) for c in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


class ProbeError(ValueError):
    pass


def validate_url(value: str, *, private_http: bool = False, mcp: bool = False) -> str:
    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ProbeError("Invalid URL") from exc
    if parsed.username or parsed.password or parsed.fragment or parsed.query or not parsed.hostname:
        raise ProbeError("URL must not contain credentials, query or fragment")
    if parsed.scheme not in ("https", "http") or port == 0:
        raise ProbeError("Expected HTTP or HTTPS URL with a valid port")
    if parsed.scheme == "http":
        try:
            address = ipaddress.ip_address(parsed.hostname)
            local = address.is_loopback or any(address in network for network in PRIVATE_NETWORKS)
        except ValueError:
            local = parsed.hostname == "localhost"
        if mcp or not private_http or not local:
            raise ProbeError("Plain HTTP needs explicit private-only opt-in and a private IP or localhost")
    clean = value.rstrip("/")
    if mcp and parsed.path != "/mcp":
        raise ProbeError("MCP URL must end in /mcp")
    if not mcp and not parsed.path.rstrip("/").endswith("/v1"):
        raise ProbeError("Provider URL must end in /v1")
    return clean


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ProbeError("Authenticated redirects are prohibited")


def invoke(url: str, *, method="GET", headers=None, body=None, timeout=8) -> dict:
    encoded = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(url, data=encoded, headers=headers or {}, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ProbeError("Response exceeded allowed size")
        decoded = json.loads(raw)
        if not isinstance(decoded, dict):
            raise ProbeError("Expected JSON object")
        return decoded
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        if isinstance(exc, ProbeError):
            raise
        status = getattr(exc, "code", None)
        raise ProbeError("Request failed: " + type(exc).__name__ + (f" HTTP {status}" if status else "")) from exc


def probe_provider(base: str, token: str, model: str, infer: bool) -> None:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    inventory = invoke(base + "/models", headers=headers)
    items = inventory.get("data")
    if not isinstance(items, list) or not items:
        raise ProbeError("Provider returned no model inventory")
    names = {entry.get("id") for entry in items
             if isinstance(entry, dict) and isinstance(entry.get("id"), str) and entry["id"]}
    if not names:
        raise ProbeError("Provider returned no usable model identifiers")
    if model and model not in names:
        raise ProbeError("Requested model is unavailable")
    print(f"PROVIDER_MODELS=PASS count={len(names)}")
    if infer:
        if not model:
            raise ProbeError("--infer requires --model")
        result = invoke(base + "/chat/completions", method="POST",
                        headers={**headers, "Content-Type": "application/json"},
                        body={"model": model, "messages": [{"role": "user", "content": "Reply OK."}], "max_tokens": 8},
                        timeout=30)
        choices = result.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProbeError("No choices in inference response")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message, dict) or not isinstance(message.get("content"), str) or not message["content"].strip():
            raise ProbeError("Inference did not return nonempty assistant content")
        print("PROVIDER_INFERENCE=PASS")


def probe_mcp(url: str, token: str) -> None:
    if not token:
        raise ProbeError("ZWORKFORCE_MCP_TOKEN required for authorized MCP discovery")
    version = "2026-07-28"
    result = invoke(url, method="POST", headers={
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "MCP-Protocol-Version": version,
        "Mcp-Method": "server/discover",
    }, body={
        "jsonrpc": "2.0", "id": 1, "method": "server/discover",
        "params": {"_meta": {
            "io.modelcontextprotocol/protocolVersion": version,
            "io.modelcontextprotocol/clientCapabilities": {},
        }},
    })
    if (result.get("jsonrpc") != "2.0" or result.get("id") != 1
            or "error" in result or not isinstance(result.get("result"), dict)):
        raise ProbeError("MCP server/discover contract mismatch")
    print("MCP_DISCOVERY=PASS")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider-url", default="")
    parser.add_argument("--mcp-url", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--allow-private-http", action="store_true")
    parser.add_argument("--infer", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not args.provider_url and not args.mcp_url:
            raise ProbeError("Provide --provider-url or --mcp-url")
        if args.provider_url:
            base = validate_url(args.provider_url, private_http=args.allow_private_http)
            probe_provider(base, os.environ.get("ZWSLCORE_PROVIDER_TOKEN", ""), args.model, args.infer)
        if args.mcp_url:
            url = validate_url(args.mcp_url, mcp=True)
            probe_mcp(url, os.environ.get("ZWORKFORCE_MCP_TOKEN", ""))
        return 0
    except ProbeError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
