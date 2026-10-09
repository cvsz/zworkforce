import unittest

from zworkforce.mcp import (
    MCP_PROTOCOL_VERSION,
    MCP_PROTOCOL_VERSION_META_KEY,
    mcp_protocol_version,
)


class MCPProtocolNegotiationTests(unittest.TestCase):
    def test_modern_initialize(self):
        request = {
            "method": "initialize",
            "params": {"protocolVersion": MCP_PROTOCOL_VERSION},
        }
        self.assertEqual(
            mcp_protocol_version(request, MCP_PROTOCOL_VERSION),
            MCP_PROTOCOL_VERSION,
        )

    def test_legacy_initialize(self):
        request = {
            "method": "initialize",
            "params": {"protocolVersion": "2025-11-25"},
        }
        self.assertEqual(
            mcp_protocol_version(request),
            "2025-11-25",
        )

    def test_unsupported_initialize(self):
        request = {
            "method": "initialize",
            "params": {"protocolVersion": "2099-01-01"},
        }
        self.assertIsNone(
            mcp_protocol_version(request, "2099-01-01"),
        )

    def test_header_metadata_mismatch(self):
        request = {
            "method": "tools/list",
            "params": {
                "_meta": {
                    MCP_PROTOCOL_VERSION_META_KEY: MCP_PROTOCOL_VERSION,
                }
            },
        }
        self.assertIsNone(
            mcp_protocol_version(request, "2025-11-25"),
        )


if __name__ == "__main__":
    unittest.main()
