import unittest
from unittest.mock import patch
from zworkforce.samsung_manifest import analyze
from zworkforce.mcp import handle_mcp, MCP_TOOLS

class SamsungManifestTests(unittest.TestCase):
    def test_manifest(self):
        record = {"name": "kernel.tar.gz", "license": "GPL-2.0-only", "sha256": "a" * 64}
        result = analyze("UA40F5500AR", [record])
        self.assertFalse(result["licenses_verified"])
        self.assertFalse(result["checksums_verified"])
        self.assertFalse(result["packages"][0]["verified"])

    def test_invalid(self):
        with self.assertRaises(ValueError):
            analyze("UA40F5500AR", [{"name": "../bad", "license": "GPL-2.0-only", "sha256": "a" * 64}])
        with self.assertRaises(ValueError):
            analyze("UA40F5500AR", [{}])
        with self.assertRaises(ValueError):
            analyze("ßa", [])

    def test_mcp_authorization(self):
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": "samsung.source_manifest", "arguments": {"model": "UA40F5500AR", "packages": []}}}
        with patch("zworkforce.mcp.AuthManager.require", return_value=False):
            self.assertTrue(handle_mcp(None, object(), "t", request)["result"]["isError"])
        with patch("zworkforce.mcp.AuthManager.require", return_value=True):
            self.assertFalse(handle_mcp(None, object(), "t", request)["result"]["isError"])
        self.assertTrue(MCP_TOOLS["samsung.source_manifest"]["annotations"]["readOnlyHint"])

if __name__ == "__main__":
    unittest.main()
