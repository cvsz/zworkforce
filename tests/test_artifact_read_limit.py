from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from zworkforce.artifacts import ArtifactTooLargeError, LocalArtifactStore, S3ArtifactStore


class ArtifactReadLimitTests(unittest.TestCase):
    def test_local_artifact_read_obeys_limit(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "payload"
            path.write_bytes(b"12345")
            store = LocalArtifactStore(root)

            self.assertEqual(store.read_bytes(path.as_uri(), max_bytes=5), b"12345")
            with self.assertRaises(ArtifactTooLargeError):
                store.read_bytes(path.as_uri(), max_bytes=4)

    def test_s3_artifact_read_is_bounded_and_closes_body(self):
        body = io.BytesIO(b"12345")
        store = object.__new__(S3ArtifactStore)
        store.bucket = "artifacts"
        store.prefix = "zworkforce"
        store.client = SimpleNamespace(
            get_object=lambda **_kwargs: {"Body": body},
        )

        with self.assertRaises(ArtifactTooLargeError):
            store.read_bytes("s3://artifacts/zworkforce/t/a", max_bytes=4)
        self.assertTrue(body.closed)

    def test_bounded_read_still_checks_digest(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "payload"
            content = b"safe"
            path.write_bytes(content)
            store = LocalArtifactStore(root)
            digest = hashlib.sha256(content).hexdigest()

            self.assertEqual(store.read_bytes(path.as_uri(), digest, max_bytes=4), content)


if __name__ == "__main__":
    unittest.main()
