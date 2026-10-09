import unittest

from zworkforce.mcp import (
    MCP_CLIENT_CAPABILITIES_META_KEY,
    MCP_LEGACY_PROTOCOL_VERSION,
    MCP_PROTOCOL_VERSION,
    MCP_PROTOCOL_VERSION_META_KEY,
    MCP_SUPPORTED_PROTOCOL_VERSIONS,
    handle_mcp,
    mcp_protocol_version,
)


class MCPProtocolNegotiationTests(unittest.TestCase):
    def test_initialize_counter_offer_from_modern(self):
        request = {"method": "initialize", "params": {"protocolVersion": MCP_PROTOCOL_VERSION}}
        self.assertEqual(mcp_protocol_version(request, MCP_PROTOCOL_VERSION), MCP_LEGACY_PROTOCOL_VERSION)
        result = handle_mcp(None, None, "tenant", request, protocol_version=MCP_LEGACY_PROTOCOL_VERSION)
        self.assertEqual(result["result"]["protocolVersion"], MCP_LEGACY_PROTOCOL_VERSION)
        self.assertIn("serverInfo", result["result"])

    def test_initialize_counter_offer_from_unknown(self):
        request = {"method": "initialize", "params": {"protocolVersion": "2099-01-01"}}
        self.assertEqual(mcp_protocol_version(request, "2099-01-01"), MCP_LEGACY_PROTOCOL_VERSION)

    def test_legacy_initialize(self):
        request = {"method": "initialize", "params": {"protocolVersion": "2025-06-18"}}
        self.assertEqual(mcp_protocol_version(request), "2025-06-18")

    def test_unsupported_sse_only_revision_not_advertised(self):
        self.assertNotIn("2024-11-05", MCP_SUPPORTED_PROTOCOL_VERSIONS)
        request = {"method": "tools/list", "params": {}}
        self.assertIsNone(mcp_protocol_version(request, "2024-11-05"))

    def test_modern_metadata_capabilities_required(self):
        for value in (None, "bad", [], True):
            with self.subTest(value=value):
                metadata = {MCP_PROTOCOL_VERSION_META_KEY: MCP_PROTOCOL_VERSION}
                if value is not None:
                    metadata[MCP_CLIENT_CAPABILITIES_META_KEY] = value
                request = {"method": "tools/call", "params": {
                    "name": "workforce.submit_task", "arguments": {}, "_meta": metadata,
                }}
                self.assertIsNone(mcp_protocol_version(request, MCP_PROTOCOL_VERSION))

    def test_modern_metadata_capabilities_object_accepted(self):
        request = {"method": "tools/list", "params": {"_meta": {
            MCP_PROTOCOL_VERSION_META_KEY: MCP_PROTOCOL_VERSION,
            MCP_CLIENT_CAPABILITIES_META_KEY: {},
        }}}
        self.assertEqual(mcp_protocol_version(request, MCP_PROTOCOL_VERSION), MCP_PROTOCOL_VERSION)

    def test_header_metadata_mismatch(self):
        request = {"method": "tools/list", "params": {"_meta": {
            MCP_PROTOCOL_VERSION_META_KEY: MCP_PROTOCOL_VERSION,
            MCP_CLIENT_CAPABILITIES_META_KEY: {},
        }}}
        self.assertIsNone(mcp_protocol_version(request, "2025-11-25"))


if __name__ == "__main__":
    unittest.main()
