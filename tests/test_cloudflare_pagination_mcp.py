import unittest
import json
import os
from unittest.mock import patch
from zworkforce.cloudflare_live import read, CloudflareReadError
from zworkforce.mcp import MCP_TOOLS

class CloudflarePaginationTests(unittest.TestCase):
    def test_bounded_pages(self):
        for page in (0, 11, -1, True, "2"):
            with self.subTest(page=page), self.assertRaises(CloudflareReadError):
                read("tenant", "zones", page=page)

    def test_provider_metadata_is_tenant_safe(self):
        from zworkforce import cloudflare_live
        zid = "a" * 32
        aid = "b" * 32
        config = {"tenant-a": {"zone_ids": [zid], "account_ids": [aid],
                               "token_env": "ZWORKFORCE_CF_TOKEN_TEST"}}
        class Response:
            status = 200
            is_zone = False
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, size):
                return json.dumps({"success": True, "result": {"id": zid} if self.is_zone else [{"id": zid}],
                    "result_info": {"total_pages": 10, "total_count": 99}}).encode()
        class Opener:
            def open(self, req, timeout):
                response = Response()
                response.is_zone = "/zones/" in req.full_url
                return response
        with patch.dict(os.environ, {"ZWORKFORCE_CLOUDFLARE_READ_TENANTS": json.dumps(config),
                                      "ZWORKFORCE_CF_TOKEN_TEST": "test"}):
            with patch("zworkforce.cloudflare_live.urllib.request.build_opener", return_value=Opener()):
                self.assertFalse(cloudflare_live.read("tenant-a", "zones")["has_more"])
                self.assertEqual(cloudflare_live.read("tenant-a", "zones", page=2)["items"], [])
                self.assertTrue(cloudflare_live.read("tenant-a", "tunnels", aid)["has_more"])

    def test_schema(self):
        schema = MCP_TOOLS["cloudflare.live_inventory"]["inputSchema"]
        self.assertEqual(schema["properties"]["page"]["maximum"], 10)

if __name__ == "__main__":
    unittest.main()
