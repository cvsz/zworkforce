import unittest
from unittest.mock import patch
from zworkforce.samsung_sdk_probe import inspect_environment
from zworkforce.mcp import MCP_TOOLS, handle_mcp


class SamsungSdkProbeTests(unittest.TestCase):
    def test_unconfigured(self):
        result = inspect_environment("samsung-legacy", {})
        self.assertFalse(result["configured"])
        self.assertFalse(result["sdk_verified"])
        self.assertEqual(result["executed_commands"], [])

    def test_no_secret_or_path_echo(self):
        result = inspect_environment("tizen", {"TIZEN_STUDIO_HOME": "/private/location/secret"})
        self.assertTrue(result["configured"])
        self.assertNotIn("/private/location/secret", str(result))

    def test_invalid_platform(self):
        with self.assertRaises(ValueError):
            inspect_environment("../tizen", {})

    def test_authorization(self):
        req = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": "samsung.sdk_environment", "arguments": {"platform": "tizen"}}}
        with patch("zworkforce.mcp.AuthManager.require", return_value=False):
            self.assertTrue(handle_mcp(None, object(), "tenant", req)["result"]["isError"])
        with patch("zworkforce.mcp.AuthManager.require", return_value=True):
            self.assertFalse(handle_mcp(None, object(), "tenant", req)["result"]["isError"])
        self.assertTrue(MCP_TOOLS["samsung.sdk_environment"]["annotations"]["readOnlyHint"])


if __name__ == "__main__":
    unittest.main()
