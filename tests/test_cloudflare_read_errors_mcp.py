import json
import os
import unittest
import urllib.error
from unittest.mock import patch

from zworkforce.cloudflare_live import CloudflareReadError, read

ZONE = "a" * 32
CONFIG = {"tenant-a": {"zone_ids": [ZONE], "account_ids": [], "token_env": "ZWORKFORCE_CF_TOKEN_TEST"}}


class FailedOpener:
    def __init__(self, status):
        self.status = status

    def open(self, request, timeout):
        raise urllib.error.HTTPError(request.full_url, self.status, "failed", {}, None)


class CloudflareReadErrorsTests(unittest.TestCase):
    def test_rate_limit_redacts_provider_response(self):
        with patch.dict(os.environ, {"ZWORKFORCE_CLOUDFLARE_READ_TENANTS": json.dumps(CONFIG),
                                      "ZWORKFORCE_CF_TOKEN_TEST": "secret-test-token"}):
            for status in (429, 500, 401, 403):
                with self.subTest(status=status):
                    with patch("zworkforce.cloudflare_live.urllib.request.build_opener", return_value=FailedOpener(status)):
                        with self.assertRaises((CloudflareReadError, PermissionError)) as error:
                            read("tenant-a", "zones")
                        self.assertNotIn("secret-test-token", str(error.exception))
                        self.assertNotIn("https://", str(error.exception))
                        if status == 429:
                            self.assertIn("rate limit", str(error.exception))


if __name__ == "__main__":
    unittest.main()
