import unittest
from unittest.mock import patch

from zworkforce.samsung_compat import compatibility
from zworkforce.mcp import handle_mcp as _handle_mcp, MCP_LEGACY_PROTOCOL_VERSION




def handle_mcp(*args, **kwargs):
    """Legacy protocol fixture for direct MCP handler unit tests."""
    kwargs.setdefault("protocol_version", MCP_LEGACY_PROTOCOL_VERSION)
    return _handle_mcp(*args, **kwargs)

class SamsungCompatibilityTests(unittest.TestCase):
    def test_legacy(self):
        result = compatibility("UA40F5500AR", 2013)
        self.assertEqual(result["platform_by_year"], "samsung-legacy")
        self.assertFalse(result["device_compatibility_verified"])
        self.assertFalse(result["usb_installation_confirmed"])

    def test_tizen(self):
        self.assertEqual(compatibility("TV2024", 2024)["platform_by_year"], "tizen")

    def test_invalid(self):
        for model, year in (("../x", 2013), ("ßa", 2013), ("AA", True), ("AA", 2009)):
            with self.subTest(model=model, year=year), self.assertRaises(ValueError):
                compatibility(model, year)

    def test_mcp_auth(self):
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": "samsung.compatibility",
                              "arguments": {"model": "UA40F5500AR", "model_year": 2013}}}
        with patch("zworkforce.mcp.AuthManager.require", return_value=False):
            self.assertTrue(handle_mcp(None, object(), "t", request)["result"]["isError"])
        with patch("zworkforce.mcp.AuthManager.require", return_value=True) as guard:
            result = handle_mcp(None, object(), "t", request)
            self.assertFalse(result["result"]["isError"])
            guard.assert_called_once()
            self.assertEqual(guard.call_args.args[1:], ("viewer", "workforce:read"))


if __name__ == "__main__":
    unittest.main()
