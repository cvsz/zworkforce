#!/usr/bin/env python3
"""
Stage F Vault + S3 setup automation for zWorkforce v3.0.4.

Adds repository root to sys.path so zworkforce package is importable
without requiring PYTHONPATH.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

VAULT_ADDR = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
VAULT_TOKEN = os.getenv("VAULT_TOKEN", "zworkforce-local-token")
VAULT_BIN = os.path.expanduser(os.getenv("VAULT_BIN", "~/bin/vault"))
SUPABASE_ACCESS_TOKEN = os.getenv("SUPABASE_ACCESS_TOKENS", "")
PROJECT_REF = "aqbtiobrpwstjbbwtqap"
BUCKET = "zworkforce"
S3_ENDPOINT = f"https://{PROJECT_REF}.storage.supabase.co/storage/v1/s3"
import json
import os
import subprocess
import sys
import urllib.request
from typing import Any

VAULT_ADDR = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
VAULT_TOKEN = os.getenv("VAULT_TOKEN", "zworkforce-local-token")
VAULT_BIN = os.path.expanduser(os.getenv("VAULT_BIN", "~/bin/vault"))
SUPABASE_ACCESS_TOKEN = os.getenv("SUPABASE_ACCESS_TOKENS", "")
PROJECT_REF = "aqbtiobrpwstjbbwtqap"
BUCKET = "zworkforce"
S3_ENDPOINT = f"https://{PROJECT_REF}.storage.supabase.co/storage/v1/s3"


def fail(message: str) -> None:
    print(f"FATAL: {message}", file=sys.stderr)
    sys.exit(1)


def supabase_api_get(path: str) -> dict[str, Any]:
    """Call Supabase Management API with PAT."""
    if not SUPABASE_ACCESS_TOKEN:
        fail("SUPABASE_ACCESS_TOKENS environment variable is not set")
    url = f"https://api.supabase.com/v1/{path.lstrip('/')}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read(1024).decode(errors="replace")
        fail(f"Supabase API {path} failed HTTP {exc.code}: {body[:300]}")
    except Exception as exc:
        fail(f"Supabase API {path} error: {exc}")


def vault_write(path: str, data: dict[str, str]) -> None:
    """Write key/value secrets to Vault KV v2."""
    cmd = [VAULT_BIN, "kv", "put", path] + [f"{k}={v}" for k, v in data.items()]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        fail(f"Vault write {path} failed: {result.stderr.strip()}")


def vault_read_field(path: str, field: str) -> str:
    """Read a single field from Vault KV v2."""
    cmd = [VAULT_BIN, "kv", "get", "-format=json", path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        fail(f"Vault read {path} failed: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    return data["data"]["data"][field]


def stage_f_test(access_key: str, secret_key: str) -> None:
    """Run Stage F S3 write/read/SHA-256 verification."""
    from zworkforce.artifacts import S3ArtifactStore

    os.environ["AWS_ACCESS_KEY_ID"] = access_key
    os.environ["AWS_SECRET_ACCESS_KEY"] = secret_key

    store = S3ArtifactStore(BUCKET, prefix="stagef", endpoint_url=S3_ENDPOINT, db=None)

    data = b"Stage F Supabase Vault verification payload " * 100
    expected_sha256 = hashlib.sha256(data).hexdigest()

    artifact = store.put_bytes(
        "tenant-stagef", "vault-test.bin", data, actor="test",
        content_type="application/octet-stream",
    )
    assert artifact["sha256"] == expected_sha256, "put sha256 mismatch"
    assert artifact["size_bytes"] == len(data), "size mismatch"
    assert artifact["storage_uri"].startswith(f"s3://{BUCKET}/"), "unexpected uri"

    body = store.read_bytes(artifact["storage_uri"], expected_sha256=expected_sha256)
    assert body == data, "read content mismatch"
    assert hashlib.sha256(body).hexdigest() == expected_sha256, "read sha256 mismatch"

    key = artifact["storage_uri"].split(f"{BUCKET}/", 1)[1]
    store.client.delete_object(Bucket=BUCKET, Key=key)

    print("STAGE_F_VAULT_S3_WRITE_READ_SHA256: PASS")


def main() -> None:
    if not SUPABASE_ACCESS_TOKEN:
        fail("SUPABASE_ACCESS_TOKENS is not set. Export your Supabase PAT first.")

    print(f"[1/3] Querying Supabase project {PROJECT_REF} ...")
    project = supabase_api_get(f"projects/{PROJECT_REF}")
    print(f"    Project: {project.get('name', PROJECT_REF)} (status: {project.get('status', 'unknown')})")

    print("[2/3] Writing Supabase S3 credentials to Vault ...")
    # Note: Supabase S3 credentials are typically obtained via Supabase CLI
    # or Storage API. Here we write placeholder structure; operator must
    # populate real values via 'vault kv put' with actual S3 credentials.
    vault_write("secret/data/zworkforce/supabase-s3", {
        "access_key": os.getenv("SUPABASE_S3_ACCESS_KEY", "REQUIRED_REAL_VALUE"),
        "secret_key": os.getenv("SUPABASE_S3_SECRET_KEY", "REQUIRED_REAL_VALUE"),
    })
    vault_write("secret/data/zworkforce/supabase-database", {
        "password": os.getenv("SUPABASE_DB_PASSWORD", "REQUIRED_REAL_VALUE"),
    })
    vault_write("secret/data/zworkforce/supabase", {
        "publishable_key": os.getenv("SUPABASE_PUBLISHABLE_KEY", "REQUIRED_REAL_VALUE"),
        "secret_key": os.getenv("SUPABASE_SECRET_KEY", "REQUIRED_REAL_VALUE"),
    })
    print("    Vault paths written (replace placeholder values with real credentials)")

    print("[3/3] Stage F requires real S3 credentials ...")
    access_key = os.getenv("SUPABASE_S3_ACCESS_KEY", "")
    secret_key = os.getenv("SUPABASE_S3_SECRET_KEY", "")
    if not access_key or not secret_key or "REQUIRED" in access_key or "REQUIRED" in secret_key:
        print("    SKIPPED: Set SUPABASE_S3_ACCESS_KEY and SUPABASE_S3_SECRET_KEY env vars")
        print("    with real Supabase S3 credentials, then re-run Stage F test.")
        sys.exit(0)

    stage_f_test(access_key, secret_key)


if __name__ == "__main__":
    main()
