import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cme_verifier", ROOT / "scripts" / "verify-cme-production.py")
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class FakeResponse:
    status = 200

    def __init__(self, url, body):
        self.url = url
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def geturl(self):
        return self.url

    def read(self):
        return json.dumps(self.body).encode()


class FakeOpener:
    def __init__(self, url=None, body=None):
        self.url = url
        self.body = {"release": "abc"} if body is None else body

    def open(self, request, timeout):
        return FakeResponse(self.url or request.full_url, self.body)


class CMEVerifierTests(unittest.TestCase):
    def test_missing_access_credentials_rejected(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "Access credentials"):
                verifier.fetch_json("https://cme.zeaz.dev/release", 1, "cme.zeaz.dev")

    def test_external_or_insecure_urls_rejected(self):
        with patch.dict(os.environ, {"ZWORKFORCE_ACCESS_ID": "id", "ZWORKFORCE_ACCESS_TOKEN": "token"}):
            for url in ("http://cme.zeaz.dev/release", "https://evil.example/release",
                        "https://cme.zeaz.dev:8443/release"):
                with self.subTest(url=url), self.assertRaises(RuntimeError):
                    verifier.fetch_json(url, 1, "cme.zeaz.dev")

    def test_success_requires_access_headers(self):
        with patch.dict(os.environ, {"ZWORKFORCE_ACCESS_ID": "id", "ZWORKFORCE_ACCESS_TOKEN": "token"}):
            opener = FakeOpener()
            with patch.object(verifier.urllib.request, "build_opener", return_value=opener) as patched:
                status, result = verifier.fetch_json("https://cme.zeaz.dev/release", 1, "cme.zeaz.dev")
            self.assertEqual(status, 200)
            self.assertEqual(result["release"], "abc")
            self.assertIs(patched.call_args.args[0], verifier.NoRedirect)

    def test_redirect_to_other_host_rejected(self):
        with patch.dict(os.environ, {"ZWORKFORCE_ACCESS_ID": "id", "ZWORKFORCE_ACCESS_TOKEN": "token"}):
            with patch.object(verifier.urllib.request, "build_opener",
                              return_value=FakeOpener("https://evil.example/steal")):
                with self.assertRaisesRegex(RuntimeError, "redirected"):
                    verifier.fetch_json("https://cme.zeaz.dev/release", 1, "cme.zeaz.dev")

    def test_non_object_json_rejected(self):
        with patch.dict(os.environ, {"ZWORKFORCE_ACCESS_ID": "id", "ZWORKFORCE_ACCESS_TOKEN": "token"}):
            with patch.object(verifier.urllib.request, "build_opener",
                              return_value=FakeOpener(body=["invalid"])):
                with self.assertRaisesRegex(RuntimeError, "JSON object"):
                    verifier.fetch_json("https://cme.zeaz.dev/release", 1, "cme.zeaz.dev")

    def test_immutable_evidence_write(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "evidence.json"
            verifier.write_evidence(path, {"result": "FAIL", "approval_reference": "run-123"})
            self.assertEqual(json.loads(path.read_text())["approval_reference"], "run-123")
            with self.assertRaises(FileExistsError):
                verifier.write_evidence(path, {"result": "PASS"})


if __name__ == "__main__":
    unittest.main()
