from __future__ import annotations

import hashlib
import mimetypes
import os
from pathlib import Path
from typing import Any


class ArtifactError(RuntimeError):
    pass


class ArtifactTooLargeError(ArtifactError):
    pass


def _read_limited(stream, max_bytes: int | None) -> bytes:
    data = stream.read(max_bytes + 1 if max_bytes is not None else -1)
    if max_bytes is not None and len(data) > max_bytes:
        raise ArtifactTooLargeError("artifact exceeds the configured read limit")
    return data


class LocalArtifactStore:
    def __init__(self, root: str | Path, db=None):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = db

    def put_bytes(self, tenant_id: str, name: str, data: bytes, *, actor: str, content_type: str | None = None,
                  task_id: str | None = None, workflow_run_id: str | None = None,
                  metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        if not name or len(name) > 255:
            raise ArtifactError("artifact name must contain 1..255 characters")
        digest = hashlib.sha256(data).hexdigest()
        path = self.root / tenant_id / digest[:2] / digest
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)
        artifact = {
            "name": name,
            "content_type": content_type or mimetypes.guess_type(name)[0] or "application/octet-stream",
            "storage_uri": "file://" + str(path),
            "sha256": digest,
            "size_bytes": len(data),
            "task_id": task_id,
            "workflow_run_id": workflow_run_id,
            "metadata": metadata or {},
        }
        return self.db.register_artifact(tenant_id, artifact, actor) if self.db else artifact

    def put_file(self, tenant_id: str, source: str | Path, *, actor: str, **kwargs: Any) -> dict[str, Any]:
        source = Path(source)
        if not source.is_file():
            raise ArtifactError("artifact source file not found")
        return self.put_bytes(tenant_id, source.name, source.read_bytes(), actor=actor, **kwargs)

    def read_bytes(
        self, storage_uri: str, expected_sha256: str = "", *, max_bytes: int | None = None
    ) -> bytes:
        if max_bytes is not None and (type(max_bytes) is not int or max_bytes < 0):
            raise ValueError("max_bytes must be a non-negative integer")
        if not storage_uri.startswith("file://"):
            raise ArtifactError("local artifact store only accepts file:// URIs")
        path = Path(storage_uri[7:]).resolve()
        if self.root != path and self.root not in path.parents:
            raise ArtifactError("artifact path escapes store root")
        with path.open("rb") as source:
            data = _read_limited(source, max_bytes)
        if expected_sha256 and hashlib.sha256(data).hexdigest() != expected_sha256:
            raise ArtifactError("artifact integrity check failed")
        return data


class S3ArtifactStore:
    """S3-compatible content-addressed artifact backend. Install zworkforce[s3]."""

    def __init__(self, bucket: str, prefix: str = "zworkforce", endpoint_url: str | None = None, db=None):
        try:
            import boto3
        except ImportError as exc:
            raise ArtifactError("S3 backend requires `pip install zworkforce[s3]`") from exc
        if not bucket:
            raise ArtifactError("ZWORKFORCE_S3_BUCKET is required")
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = boto3.client("s3", endpoint_url=endpoint_url or None)
        self.db = db

    def put_bytes(self, tenant_id: str, name: str, data: bytes, *, actor: str, content_type: str | None = None,
                  task_id: str | None = None, workflow_run_id: str | None = None,
                  metadata: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
        if not name or len(name) > 255:
            raise ArtifactError("artifact name must contain 1..255 characters")
        digest = hashlib.sha256(data).hexdigest()
        key = f"{self.prefix}/{tenant_id}/{digest[:2]}/{digest}"
        content_type = content_type or mimetypes.guess_type(name)[0] or "application/octet-stream"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type,
                               Metadata={"sha256": digest, "actor": actor[:256], "name": name[:256]})
        artifact = {"name": name, "content_type": content_type, "storage_uri": f"s3://{self.bucket}/{key}",
                    "sha256": digest, "size_bytes": len(data), "task_id": task_id,
                    "workflow_run_id": workflow_run_id, "metadata": metadata or {}}
        return self.db.register_artifact(tenant_id, artifact, actor) if self.db else artifact

    def put_file(self, tenant_id: str, source: str | Path, *, actor: str, **kwargs: Any) -> dict[str, Any]:
        source = Path(source)
        if not source.is_file():
            raise ArtifactError("artifact source file not found")
        return self.put_bytes(tenant_id, source.name, source.read_bytes(), actor=actor, **kwargs)

    def read_bytes(
        self, storage_uri: str, expected_sha256: str = "", *, max_bytes: int | None = None
    ) -> bytes:
        if max_bytes is not None and (type(max_bytes) is not int or max_bytes < 0):
            raise ValueError("max_bytes must be a non-negative integer")
        prefix = f"s3://{self.bucket}/"
        if not storage_uri.startswith(prefix):
            raise ArtifactError("S3 artifact URI does not belong to configured bucket")
        key = storage_uri[len(prefix):]
        body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"]
        try:
            data = _read_limited(body, max_bytes)
        finally:
            close = getattr(body, "close", None)
            if close:
                close()
        body = data
        if expected_sha256 and hashlib.sha256(body).hexdigest() != expected_sha256:
            raise ArtifactError("artifact integrity check failed")
        return body


def build_artifact_store(settings, db):
    backend = os.getenv("ZWORKFORCE_ARTIFACT_BACKEND", "local").strip().lower()
    if backend == "local":
        return LocalArtifactStore(os.getenv("ZWORKFORCE_ARTIFACT_DIR", str(settings.data_dir / "artifacts")), db)
    if backend == "s3":
        return S3ArtifactStore(
            os.getenv("ZWORKFORCE_S3_BUCKET", ""),
            os.getenv("ZWORKFORCE_S3_PREFIX", "zworkforce"),
            os.getenv("ZWORKFORCE_S3_ENDPOINT_URL", "") or None,
            db,
        )
    raise ArtifactError("ZWORKFORCE_ARTIFACT_BACKEND must be local or s3")
