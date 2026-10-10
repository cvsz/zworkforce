import unittest
from unittest.mock import patch
from types import SimpleNamespace
from zworkforce.samsung_builder_preflight import assess
from zworkforce.mcp import handle_mcp


class SamsungBuilderPreflightTests(unittest.TestCase):
    def test_legacy_never_claims_ready(self):
        result = assess("UA40F5500AR", 2013)
        self.assertEqual(result["platform"], "samsung-legacy")
        self.assertFalse(result["ready_to_build"])
        self.assertFalse(result["build_executed"])
        self.assertFalse(result["signing_verified"])

    def test_mcp_rbac(self):
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": "samsung.builder_preflight",
                              "arguments": {"model": "UA40F5500AR", "model_year": 2013}}}
        with patch("zworkforce.mcp.AuthManager.require", return_value=False):
            self.assertTrue(handle_mcp(None, object(), "t", request, protocol_version="2025-11-25")["result"]["isError"])
        with patch("zworkforce.mcp.AuthManager.require", return_value=True):
            self.assertFalse(handle_mcp(None, object(), "t", request, protocol_version="2025-11-25")["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
