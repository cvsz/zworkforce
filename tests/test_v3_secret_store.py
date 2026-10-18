import json
import os
import tempfile
import unittest
from pathlib import Path

from zworkforce.secret_store import SecretResolver, SecretStoreError


class SecretStoreTests(unittest.TestCase):
    def test_env_and_file_json_field(self):
        os.environ["ZWF_TEST_SECRET"]="value-123"
        self.assertEqual(SecretResolver().resolve("env://ZWF_TEST_SECRET"),"value-123")
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"secret.json";p.write_text(json.dumps({"token":"abc"}))
            self.assertEqual(SecretResolver().resolve(p.as_uri()+"#token"),"abc")
    def test_unsupported_scheme_rejected(self):
        with self.assertRaises(SecretStoreError): SecretResolver().resolve("ftp://example/secret")
    def test_file_reference_rejects_authority_and_relative_traversal(self):
        """A `file://` reference must not smuggle a host or a relative path."""
        resolver=SecretResolver()
        # `..` in the authority silently produced a relative path that escaped
        # the working directory before this guard existed.
        for ref in ("file://../../etc/passwd",
                    "file://evilhost/etc/passwd",
                    "file://example.com/secret"):
            with self.assertRaises(SecretStoreError, msg=ref):
                resolver.resolve(ref)
        with self.assertRaises(SecretStoreError):
            resolver.resolve("file://relative/secret")
        with self.assertRaises(SecretStoreError):
            resolver.resolve("file://")
    def test_file_reference_still_accepts_absolute_and_localhost(self):
        resolver=SecretResolver()
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"secret.txt";p.write_text("value-456")
            self.assertEqual(resolver.resolve(p.as_uri()),"value-456")
            self.assertEqual(resolver.resolve("file://localhost"+str(p)),"value-456")

if __name__=="__main__": unittest.main()
