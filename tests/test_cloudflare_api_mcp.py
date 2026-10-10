import unittest
from unittest.mock import patch

from zworkforce import cloudflare_api
from zworkforce.mcp import MCP_TOOLS, handle_mcp as _handle_mcp, MCP_LEGACY_PROTOCOL_VERSION




def handle_mcp(*args, **kwargs):
    """Legacy protocol fixture for direct MCP handler unit tests."""
    kwargs.setdefault("protocol_version", MCP_LEGACY_PROTOCOL_VERSION)
    return _handle_mcp(*args, **kwargs)

class CloudflareAPIMCPTests(unittest.TestCase):
    def call(self, name, args, allowed=True):
        with patch("zworkforce.mcp.AuthManager.require", return_value=allowed) as check:
            result = handle_mcp(None, object(), "tenant-a", {
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": name, "arguments": args},
            })
            check.assert_called_once()
            self.assertEqual(check.call_args.args[1:], ("viewer", "workforce:read"))
            return result

    def test_discovery(self):
        self.assertIn("cloudflare.references", MCP_TOOLS)
        self.assertIn("cloudflare.operation_plan", MCP_TOOLS)
        self.assertTrue(MCP_TOOLS["cloudflare.operation_plan"]["annotations"]["readOnlyHint"])
        result = self.call("cloudflare.references", {})
        self.assertFalse(result["result"]["isError"])
        self.assertFalse(result["result"]["structuredContent"]["execution_available"])

    def test_operation_plan(self):
        result = self.call("cloudflare.operation_plan", {"operation": "dns.create"})
        value = result["result"]["structuredContent"]
        self.assertFalse(value["execute"])
        self.assertTrue(value["requires_explicit_approval"])
        self.assertTrue(value["requires_resource_ownership_evidence"])
        read = cloudflare_api.operation_plan("dns.list")
        self.assertFalse(read["requires_explicit_approval"])

    def test_canonical_permissions(self):
        expected = {
            "dns.list": "DNS Read",
            "dns.create": "DNS Write",
            "dns.delete": "DNS Write",
            "zone.get": "Zone Read",
            "tunnel.list": "Cloudflare Tunnel Read",
            "tunnel.create": "Cloudflare Tunnel Write",
        }
        for name, permission in expected.items():
            with self.subTest(operation=name):
                self.assertEqual(cloudflare_api.operation_plan(name)["permission"], permission)

    def test_unauthorized(self):
        for name, args in (("cloudflare.references", {}),
                           ("cloudflare.operation_plan", {"operation": "dns.list"})):
            with self.subTest(name=name):
                result = self.call(name, args, allowed=False)
                self.assertTrue(result["result"]["isError"])

    def test_reject_unknown_operations(self):
        for value in ("../token", "tokens.export", "DNS.LIST", "x" * 128, "tunnel.delete"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cloudflare_api.operation_plan(value)

    def test_no_arbitrary_arguments(self):
        result = self.call("cloudflare.operation_plan", {"operation": "dns.list", "url": "https://evil.example"})
        self.assertTrue(result["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
