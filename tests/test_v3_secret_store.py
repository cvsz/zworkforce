import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zworkforce.secret_store import SecretResolver, SecretStoreError


class SecretStoreTests(unittest.TestCase):
    def test_env_and_file_json_field(self):
        with patch.dict(os.environ, {"ZWF_TEST_SECRET": "value-123"}):
            self.assertEqual(SecretResolver().resolve("env://ZWF_TEST_SECRET"), "value-123")

        with tempfile.TemporaryDirectory() as td:
            secret_path = Path(td) / "secret.json"
            secret_path.write_text(json.dumps({"token": "abc"}), encoding="utf-8")
            self.assertEqual(SecretResolver().resolve(f"{secret_path.as_uri()}#token"), "abc")

    def test_unsupported_scheme_rejected(self):
        with self.assertRaises(SecretStoreError):
            SecretResolver().resolve("ftp://example/secret")

    def test_file_reference_rejects_remote_authorities_and_relative_paths(self):
        resolver = SecretResolver()
        rejected_references = (
            "file://../../etc/passwd",
            "file://evilhost/etc/passwd",
            "file://example.com/secret",
            "file://relative/secret",
            "file://",
            "file:relative/secret",
        )
        for reference in rejected_references:
            with self.subTest(reference=reference):
                with self.assertRaises(SecretStoreError):
                    resolver.resolve(reference)

    def test_file_reference_accepts_absolute_and_loopback_paths(self):
        resolver = SecretResolver()
        with tempfile.TemporaryDirectory() as td:
            secret_path = Path(td) / "secret.txt"
            secret_path.write_text("value-456", encoding="utf-8")
            path = str(secret_path)

            references = (
                secret_path.as_uri(),
                f"file://localhost{path}",
                f"file://127.0.0.1{path}",
                f"file://[::1]{path}",
            )
            for reference in references:
                with self.subTest(reference=reference):
                    self.assertEqual(resolver.resolve(reference), "value-456")

    def test_file_reference_fails_closed_for_missing_files(self):
        with self.assertRaises(SecretStoreError):
            SecretResolver().resolve("file:///definitely-not-a-real-zeaz-secret-file")


if __name__ == "__main__":
    unittest.main()
