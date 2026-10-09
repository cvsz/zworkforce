import json
import os
import unittest
from unittest.mock import patch

from zworkforce import cloudflare_live
from zworkforce.mcp import handle_mcp


ZONE = "a" * 32
ACCOUNT = "b" * 32
CONFIG = {"tenant-a": {"zone_ids": [ZONE], "account_ids": [ACCOUNT],
                       "token_env": "ZWORKFORCE_CF_TOKEN_TEST"}}


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return json.dumps({"success": True, "result": {
            "id": ZONE, "name": "example.com", "status": "active",
            "secret": "must-not-expose"}}).encode()


class FakeOpener:
    def open(self, request, timeout):
        assert request.get_method() == "GET"
        assert request.full_url.startswith("https://api.cloudflare.com/client/v4/")
        assert timeout == 8
        return FakeResponse()


class CloudflareLiveTests(unittest.TestCase):
    def setUp(self):
        self.environ = patch.dict(os.environ, {
            "ZWORKFORCE_CLOUDFLARE_READ_TENANTS": json.dumps(CONFIG),
            "ZWORKFORCE_CF_TOKEN_TEST": "testing-token",
        })
        self.environ.start()
        self.addCleanup(self.environ.stop)

    def test_allowlisted_zone_and_redaction(self):
        with patch("zworkforce.cloudflare_live.urllib.request.build_opener", return_value=FakeOpener()):
            result = cloudflare_live.read("tenant-a", "zones")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["id"], ZONE)
        self.assertNotIn("secret", result["items"][0])
        self.assertTrue(result["partial"])

    def test_deny_unowned_and_cross_tenant(self):
        for tenant, resource, resource_id in (
            ("tenant-b", "zones", ""),
            ("tenant-a", "dns_records", "f" * 32),
            ("tenant-a", "tunnels", "f" * 32),
        ):
            with self.subTest(tenant=tenant, resource=resource):
                with self.assertRaises(PermissionError):
                    cloudflare_live.read(tenant, resource, resource_id)

    def test_reject_invalid_ids_and_methods(self):
        for resource, resource_id in (("dns_records", "../x"), ("tunnels", "x" * 32),
                                      ("zones", ZONE), ("dns.create", "")):
            with self.subTest(resource=resource):
                with self.assertRaises(cloudflare_live.CloudflareReadError):
                    cloudflare_live.read("tenant-a", resource, resource_id)

    def test_mcp_authorization(self):
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": "cloudflare.live_inventory",
                              "arguments": {"resource": "zones"}}}
        with patch("zworkforce.mcp.AuthManager.require", return_value=False):
            denied = handle_mcp(None, object(), "tenant-a", request)
        self.assertTrue(denied["result"]["isError"])
        with patch("zworkforce.mcp.AuthManager.require", return_value=True):
            with patch("zworkforce.cloudflare_live.urllib.request.build_opener", return_value=FakeOpener()):
                granted = handle_mcp(None, object(), "tenant-a", request)
        self.assertFalse(granted["result"]["isError"])
        self.assertEqual(len(granted["result"]["structuredContent"]["items"]), 1)


if __name__ == "__main__":
    unittest.main()
