import unittest
from zworkforce import samsung_tv
from zworkforce.mcp import MCP_TOOLS


class SamsungTVMCPTests(unittest.TestCase):
    def test_registry(self):
        self.assertIn("samsung.sources", MCP_TOOLS)
        self.assertIn("samsung.model_guidance", MCP_TOOLS)
        self.assertTrue(MCP_TOOLS["samsung.sources"]["annotations"]["readOnlyHint"])

    def test_catalog(self):
        entries = samsung_tv.sources()
        self.assertFalse(entries["live_verified"])
        urls = [item["url"] for item in entries["sources"]]
        self.assertIn("https://opensource.samsung.com/main", urls)
        self.assertIn("https://developer.samsung.com/smarttv/develop", urls)

    def test_model(self):
        result = samsung_tv.model_guidance("ua40f5500ar")
        self.assertEqual(result["model"], "UA40F5500AR")
        self.assertEqual(result["os_family"], "unknown")
        self.assertEqual(result["verification_status"], "unverified")

    def test_invalid_model(self):
        for value in ("", "../etc/passwd", "a b", "x" * 65):
            with self.subTest(value=value), self.assertRaises(ValueError):
                samsung_tv.model_guidance(value)


if __name__ == "__main__":
    unittest.main()
