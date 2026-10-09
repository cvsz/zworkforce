import unittest
from zworkforce.cloudflare_live import read, CloudflareReadError
from zworkforce.mcp import MCP_TOOLS

class CloudflarePaginationTests(unittest.TestCase):
    def test_bounded_pages(self):
        for page in (0, 11, -1, True, "2"):
            with self.subTest(page=page), self.assertRaises(CloudflareReadError):
                read("tenant", "zones", page=page)

    def test_schema(self):
        schema = MCP_TOOLS["cloudflare.live_inventory"]["inputSchema"]
        self.assertEqual(schema["properties"]["page"]["maximum"], 10)

if __name__ == "__main__":
    unittest.main()
