from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def fail(message: str) -> None:
    raise SystemExit(f"release gate verification failed: {message}")


def version_tuple(value: str) -> tuple[int, int, int]:
    match = _VERSION.fullmatch(value)
    if not match:
        fail("version must be a stable semantic version such as 3.0.4")
    return tuple(int(part) for part in match.groups())


def verify_url(base_url: str) -> str:
    value = base_url.strip().rstrip("/")
    parsed = urlsplit(value)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        fail("ZWORKFORCE_RELEASE_GATE_URL must be an HTTPS origin without credentials, path, query, or fragment")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed exact-SHA ARIN-Z release gate verification")
    parser.add_argument("--version", required=True, help="release version without the v prefix")
    parser.add_argument("--sha", required=True, help="full 40-character tagged commit SHA")
    args = parser.parse_args()

    version = args.version.strip()
    candidate_sha = args.sha.strip().lower()
    numeric_version = version_tuple(version)
    if not _SHA40.fullmatch(candidate_sha):
        fail("--sha must be the full 40-character Git commit SHA")

    if numeric_version < (3, 0, 4):
        print(json.dumps({"skipped": True, "version": version, "reason": "ARIN-Z release gate enforcement starts at 3.0.4"}))
        return 0

    base_url = os.getenv("ZWORKFORCE_RELEASE_GATE_URL", "")
    token = os.getenv("ZWORKFORCE_RELEASE_GATE_TOKEN", "")
    if not base_url.strip() or not token.strip():
        fail("ZWORKFORCE_RELEASE_GATE_URL and ZWORKFORCE_RELEASE_GATE_TOKEN must be configured; release verification is fail-closed")

    origin = verify_url(base_url)
    endpoint = f"{origin}/api/v1/release-gates/{version}/{candidate_sha}/verify"
    request = Request(
        endpoint,
        headers={
            "Authorization": f"Bearer {token.strip()}",
            "Accept": "application/json",
            "User-Agent": "zworkforce-release-gate-verifier/1",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=20) as response:
            if response.status != 200:
                fail(f"gate API returned HTTP {response.status}")
            raw = response.read(1_000_001)
    except HTTPError as exc:
        fail(f"gate API returned HTTP {exc.code}")
    except URLError as exc:
        fail(f"gate API could not be reached: {exc.reason}")
    if len(raw) > 1_000_000:
        fail("gate API response exceeded the permitted size")
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        fail("gate API returned invalid JSON")

    if result.get("release_version") != version:
        fail("gate API response release version does not match the tag")
    if str(result.get("candidate_sha", "")).lower() != candidate_sha:
        fail("gate API response candidate SHA does not match the tag")
    if result.get("release_ready") is not True or result.get("decision") != "GO":
        reasons = result.get("reasons") or ["the exact candidate is not GO"]
        fail("; ".join(str(reason) for reason in reasons[:12]))
    if result.get("ledger_valid") is not True:
        fail("release gate ledger integrity verification did not pass")
    if not isinstance(result.get("audit_chain"), dict) or result["audit_chain"].get("ok") is not True:
        fail("tenant audit hash-chain verification did not pass")
    if result.get("independent_approval_valid") is not True:
        fail("current independent approval is missing or invalid")
    if not _SHA256.fullmatch(str(result.get("gate_bundle_digest", ""))):
        fail("gate API did not return a valid gate bundle digest")
    if version == "3.0.4" and result.get("rollback_target") != "v3.0.3":
        fail("v3.0.4 must identify v3.0.3 as its rollback target")

    print(json.dumps({
        "verified": True,
        "release_version": version,
        "candidate_sha": candidate_sha,
        "decision": "GO",
        "gate_bundle_digest": result["gate_bundle_digest"],
        "rollback_target": result.get("rollback_target"),
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
