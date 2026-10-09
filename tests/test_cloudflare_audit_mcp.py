import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from zworkforce.mcp import handle_mcp


class CloudflareAuditTests(unittest.TestCase):
    def test_success_audited(self):
        db = Mock()
        app = SimpleNamespace(db=db)
        principal = SimpleNamespace(name="operator")
        req = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": "cloudflare.live_inventory", "arguments": {"resource": "zones"}}}
        with patch("zworkforce.mcp.AuthManager.require", return_value=True):
            with patch("zworkforce.mcp.cloudflare_live.read", return_value={"items": [], "live": True}):
                outcome = handle_mcp(app, principal, "tenant-a", req)
        self.assertFalse(outcome["result"]["isError"])
        db.audit.assert_called_once_with("tenant-a", "operator", "cloudflare.inventory.read",
                                         "zones", "", {"outcome": "success", "page": 1, "item_count": 0})

    def test_denial_audited(self):
        db = Mock()
        app = SimpleNamespace(db=db)
        principal = SimpleNamespace(name="operator")
        req = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": "cloudflare.live_inventory", "arguments": {"resource": "zones"}}}
        with patch("zworkforce.mcp.AuthManager.require", return_value=True):
            with patch("zworkforce.mcp.cloudflare_live.read", side_effect=PermissionError("not allowed")):
                outcome = handle_mcp(app, principal, "tenant-a", req)
        self.assertTrue(outcome["result"]["isError"])
        self.assertEqual(db.audit.call_args.args[-1]["outcome"], "denied_or_failed")


if __name__ == "__main__":
    unittest.main()
