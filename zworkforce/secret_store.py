from __future__ import annotations

import json
import os
from pathlib import Path
import urllib.parse
import urllib.request


class SecretStoreError(ValueError):
    pass


class SecretResolver:
    def __init__(self, *, vault_addr: str = "", vault_token: str = "", aws_region: str = ""):
        self.vault_addr = vault_addr.strip().rstrip("/")
        self.vault_token = vault_token
        self.aws_region = aws_region.strip()
        if self.vault_addr:
            parts = urllib.parse.urlsplit(self.vault_addr)
            if parts.scheme != "https" and parts.hostname not in {"localhost", "127.0.0.1", "::1"}:
                raise SecretStoreError("remote Vault endpoint must use HTTPS")

    @classmethod
    def from_env(cls) -> "SecretResolver":
        return cls(
            vault_addr=os.getenv("VAULT_ADDR", ""),
            vault_token=os.getenv("VAULT_TOKEN", ""),
            aws_region=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "")),
        )

    def resolve(self, reference: str) -> str:
        ref = str(reference or "").strip()
        if not ref:
            raise SecretStoreError("secret reference is required")
        parts = urllib.parse.urlsplit(ref)
        scheme = parts.scheme.lower()
        if scheme == "env":
            name = (parts.netloc + parts.path).lstrip("/")
            if not name or name not in os.environ:
                raise SecretStoreError(f"environment secret not found: {name}")
            return os.environ[name]
        if scheme == "file":
            # `file://../../etc/passwd` puts `..` in netloc, and
            # url2pathname(parts.path) alone silently yields a *relative*
            # path that escapes the intended directory. Require an empty or
            # localhost authority, then reject relative references outright.
            if parts.netloc and parts.netloc.lower() not in {"localhost", "127.0.0.1", "::1"}:
                raise SecretStoreError("file secret reference must not carry a remote host")
            if not parts.path or not parts.path.startswith("/"):
                raise SecretStoreError("file secret reference must be an absolute path")
            path = Path(urllib.request.url2pathname(parts.path))
            try:
                resolved = path.resolve(strict=True)
            except OSError as exc:
                raise SecretStoreError(f"cannot read secret file: {path}") from exc
            try:
                raw = resolved.read_text(encoding="utf-8")
            except OSError as exc:
                raise SecretStoreError(f"cannot read secret file: {path}") from exc
            if parts.fragment:
                try:
                    value = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise SecretStoreError("secret file field selector requires JSON") from exc
                for key in parts.fragment.split("."):
                    if not isinstance(value, dict) or key not in value:
                        raise SecretStoreError(f"secret field not found: {parts.fragment}")
                    value = value[key]
                if isinstance(value, (dict, list)):
                    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
                return str(value)
            return raw.rstrip("\r\n")
        if scheme == "vault":
            return self._vault(parts)
        if scheme in {"aws-sm", "aws-secretsmanager"}:
            return self._aws(parts)
        raise SecretStoreError(f"unsupported secret reference scheme: {scheme or '<none>'}")

    def _vault(self, parts) -> str:
        if not self.vault_addr or not self.vault_token:
            raise SecretStoreError("Vault is not configured")
        mount = parts.netloc or "secret"
        path = parts.path.lstrip("/")
        if not path:
            raise SecretStoreError("Vault secret path is required")
        url = f"{self.vault_addr}/v1/{urllib.parse.quote(mount, safe='')}/data/{urllib.parse.quote(path, safe='/')}"
        req = urllib.request.Request(url, headers={"X-Vault-Token": self.vault_token, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                payload = json.load(resp)
        except Exception as exc:
            raise SecretStoreError("Vault secret lookup failed") from exc
        data = payload.get("data", {}).get("data", {})
        field = parts.fragment or "value"
        if field not in data:
            raise SecretStoreError(f"Vault field not found: {field}")
        return str(data[field])

    def _aws(self, parts) -> str:
        secret_id = (parts.netloc + parts.path).lstrip("/")
        if not secret_id:
            raise SecretStoreError("AWS secret id is required")
        try:
            import boto3  # optional dependency
        except ImportError as exc:
            raise SecretStoreError("boto3 is required for AWS Secrets Manager references") from exc
        try:
            client = boto3.client("secretsmanager", region_name=self.aws_region or None)
            result = client.get_secret_value(SecretId=secret_id)
        except Exception as exc:
            raise SecretStoreError("AWS Secrets Manager lookup failed") from exc
        raw = result.get("SecretString")
        if raw is None:
            raise SecretStoreError("binary AWS secrets are not supported")
        if parts.fragment:
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise SecretStoreError("AWS field selector requires JSON SecretString") from exc
            if parts.fragment not in value:
                raise SecretStoreError(f"AWS secret field not found: {parts.fragment}")
            return str(value[parts.fragment])
        return str(raw)
