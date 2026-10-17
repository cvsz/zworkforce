import json
import threading
import unittest
import urllib.error
import urllib.request
from dataclasses import replace
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from common import stack

from zworkforce.api import App
from zworkforce.mcp import MCP_PROTOCOL_VERSION, MCPError, RemoteMCPClient


class MCPTests(unittest.TestCase):
    def setUp(self):
        self.temp,self.settings,self.db,self.provider,self.engine,self.auth=stack()
        self.app=App(self.settings,self.db,self.engine,self.auth,self.provider)
        self.server=ThreadingHTTPServer(("127.0.0.1",0),self.app.handler())
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.endpoint=f"http://127.0.0.1:{self.server.server_address[1]}/mcp"
        self.client=RemoteMCPClient(self.endpoint,"test-admin-secret")
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.engine.shutdown();self.temp.cleanup()
    def test_stateless_discovery_and_tools(self):
        discovery = self.client.discover()
        self.assertIn(MCP_PROTOCOL_VERSION, discovery["supportedVersions"])
        self.assertIn("tools", discovery["capabilities"])
        self.assertIn("resources", discovery["capabilities"])
        self.assertIn("_meta", discovery)
        tools = self.client.list_tools()["tools"]
        self.assertTrue(any(x["name"] == "workforce.submit_task" for x in tools))
        self.assertTrue(any(x["name"] == "workforce.install_prometa" for x in tools))
        self.assertTrue(any(x["name"] == "zchat.get_capabilities" for x in tools))
        self.assertTrue(any(x["name"] == "zchat.get_health" for x in tools))
        resources = self.client.list_resources()["resources"]
        self.assertEqual(
            {resource["uri"] for resource in resources},
            {"zchat://capabilities", "zchat://health"},
        )

    def test_zchat_health_resource_is_scoped_and_audited(self):
        self.app.settings = replace(self.settings, zchat_control_url="https://control.example.test", zchat_integration_token="z" * 48)
        health = {"status": "healthy", "database": "reachable"}
        with patch("zworkforce.zchat_integration.fetch_resource", return_value=health) as fetch:
            result = self.client.read_resource("zchat://health")
        self.assertEqual(result["contents"][0]["uri"], "zchat://health")
        self.assertEqual(json.loads(result["contents"][0]["text"]), health)
        fetch.assert_called_once_with(self.app.settings, "health")
        events = self.db.list_audit("default", limit=10)
        self.assertTrue(any(event["action"] == "zchat.health.read" for event in events))

    def test_zchat_resource_requires_workforce_read_scope(self):
        _, token = self.auth.create_key(
            "default", "limited-viewer-resource", "viewer", ["agents:read"]
        )
        client = RemoteMCPClient(self.endpoint, token)
        with (
            patch("zworkforce.zchat_integration.fetch_resource") as fetch,
            self.assertRaises(MCPError) as caught,
        ):
            client.read_resource("zchat://health")

        self.assertIsInstance(caught.exception.__cause__, urllib.error.HTTPError)
        self.assertEqual(caught.exception.__cause__.code, 403)
        fetch.assert_not_called()

    def test_zchat_resource_rejects_uncontracted_tenant_parameter(self):
        request = {
            "jsonrpc": "2.0",
            "id": 76,
            "method": "resources/read",
            "params": {
                "uri": "zchat://health",
                "tenant_id": "other",
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL_VERSION,
                    "io.modelcontextprotocol/clientCapabilities": {},
                    "io.modelcontextprotocol/clientInfo": {
                        "name": "test-client",
                        "version": "1.0",
                    },
                },
            },
        }
        with patch("zworkforce.zchat_integration.fetch_resource") as fetch:
            status, body = self._post_mcp(request, {
                "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
                "Mcp-Method": "resources/read",
                "Mcp-Name": "zchat://health",
            })

        self.assertEqual(status, 200)
        self.assertEqual(body["error"]["code"], -32602)
        self.assertIn("only uri", body["error"]["message"])
        fetch.assert_not_called()

    def test_zchat_health_tool_requires_read_scope_and_audits(self):
        self.app.settings = replace(self.settings, zchat_control_url="https://control.example.test", zchat_integration_token="z" * 48)
        health = {"status": "healthy", "database": "reachable"}
        with patch("zworkforce.zchat_integration.fetch_resource", return_value=health) as fetch:
            result = self.client.call_tool("zchat.get_health", {})
        self.assertEqual(result["structuredContent"], health)
        fetch.assert_called_once_with(self.app.settings, "health")
        events = self.db.list_audit("default", limit=10)
        self.assertTrue(any(event["action"] == "zchat.health.read" for event in events))

    def test_zchat_tools_reject_viewers_without_workforce_read_scope(self):
        _, token = self.auth.create_key(
            "default", "limited-viewer", "viewer", ["agents:read"]
        )
        client = RemoteMCPClient(self.endpoint, token)
        with (
            patch("zworkforce.zchat_integration.fetch_resource") as fetch,
            self.assertRaises(MCPError) as caught,
        ):
            client.call_tool("zchat.get_health", {})

        self.assertIsInstance(caught.exception.__cause__, urllib.error.HTTPError)
        self.assertEqual(caught.exception.__cause__.code, 403)
        fetch.assert_not_called()

    def test_zchat_tools_reject_uncontracted_arguments(self):
        with patch("zworkforce.zchat_integration.fetch_resource") as fetch:
            result = self.client.call_tool("zchat.get_health", {"tenant_id": "other"})

        self.assertTrue(result["isError"])
        self.assertIn("does not accept arguments", result["content"][0]["text"])
        fetch.assert_not_called()

    def test_standard_initialize_handshake(self):
        initialized = self.client.request("initialize", {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "clientInfo": {"name": "codex", "version": "test"},
            "capabilities": {},
        })
        # Modern initialize proposals counter-offer the latest legacy handshake.
        self.assertEqual(initialized["protocolVersion"], "2025-11-25")
        self.assertIn("tools", initialized["capabilities"])
        self.assertEqual(initialized["serverInfo"]["name"], "zworkforce")

    def _post_mcp(self, data, headers):
        request = urllib.request.Request(
            self.endpoint, data=json.dumps(data).encode(),
            headers={"Authorization": "Bearer test-admin-secret",
                     "Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            with exc:
                return exc.code, json.loads(exc.read())

    def test_modern_metadata_malformed_returns_jsonrpc_error(self):
        request = {"jsonrpc": "2.0", "id": 49, "method": "tools/list", "params": {"_meta": {
            "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL_VERSION,
        }}}
        status, body = self._post_mcp(request, {
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
            "Mcp-Method": "tools/list",
        })
        self.assertEqual(status, 400)
        self.assertEqual(body["jsonrpc"], "2.0")
        self.assertEqual(body["id"], 49)
        self.assertEqual(body["error"]["code"], -32602)

    def test_version_mismatch_returns_jsonrpc_error(self):
        request = {"jsonrpc": "2.0", "id": 50, "method": "tools/list", "params": {"_meta": {
            "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL_VERSION,
            "io.modelcontextprotocol/clientCapabilities": {},
            "io.modelcontextprotocol/clientInfo": {"name": "test-client", "version": "1.0"},
        }}}
        status, body = self._post_mcp(request, {
            "MCP-Protocol-Version": "2025-11-25",
            "Mcp-Method": "tools/list",
        })
        self.assertEqual(status, 400)
        self.assertEqual(body["id"], 50)
        self.assertEqual(body["error"]["code"], -32020)

    def test_missing_modern_version_header_returns_header_mismatch(self):
        request = {"jsonrpc": "2.0", "id": 52, "method": "tools/list", "params": {"_meta": {
            "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL_VERSION,
            "io.modelcontextprotocol/clientCapabilities": {},
            "io.modelcontextprotocol/clientInfo": {"name": "test-client", "version": "1.0"},
        }}}
        status, body = self._post_mcp(request, {"Mcp-Method": "tools/list"})
        self.assertEqual(status, 400)
        self.assertEqual(body["jsonrpc"], "2.0")
        self.assertEqual(body["id"], 52)
        self.assertEqual(body["error"]["code"], -32020)

    def test_modern_method_header_mismatch_rejected(self):
        request = {"jsonrpc": "2.0", "id": 51, "method": "tools/list", "params": {"_meta": {
            "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL_VERSION,
            "io.modelcontextprotocol/clientCapabilities": {},
            "io.modelcontextprotocol/clientInfo": {"name": "test-client", "version": "1.0"},
        }}}
        status, body = self._post_mcp(request, {
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
            "Mcp-Method": "tools/call",
        })
        self.assertEqual(status, 400)
        self.assertEqual(body["id"], 51)
        self.assertEqual(body["error"]["code"], -32020)

    def test_missing_modern_meta_returns_invalid_params(self):
        request = {"jsonrpc": "2.0", "id": 71, "method": "tools/list", "params": {}}
        status, body = self._post_mcp(request, {
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION, "Mcp-Method": "tools/list",
        })
        self.assertEqual(status, 400)
        self.assertEqual(body["id"], 71)
        self.assertEqual(body["error"]["code"], -32602)

    def test_modern_missing_header_is_mismatch(self):
        request = {"jsonrpc": "2.0", "id": 72, "method": "tools/list", "params": {"_meta": {
            "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL_VERSION,
            "io.modelcontextprotocol/clientCapabilities": {},
            "io.modelcontextprotocol/clientInfo": {"name": "test-client", "version": "1.0"},
        }}}
        status, body = self._post_mcp(request, {"Mcp-Method": "tools/list"})
        self.assertEqual(status, 400)
        self.assertEqual(body["id"], 72)
        self.assertEqual(body["error"]["code"], -32020)

    def test_unsupported_version_has_fallback_fields(self):
        request = {"jsonrpc": "2.0", "id": 73, "method": "tools/list", "params": {}}
        status, body = self._post_mcp(request, {"MCP-Protocol-Version": "2099-01-01"})
        self.assertEqual(status, 400)
        self.assertEqual(body["id"], 73)
        self.assertEqual(body["error"]["code"], -32022)
        self.assertEqual(body["error"]["data"]["requested"], "2099-01-01")
        self.assertIn("2025-03-26", body["error"]["data"]["supported"])

    def test_unknown_modern_resource_is_rejected(self):
        request = {"jsonrpc": "2.0", "id": 74, "method": "resources/read", "params": {
            "uri": "test://item", "_meta": {
                "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL_VERSION,
                "io.modelcontextprotocol/clientCapabilities": {},
            "io.modelcontextprotocol/clientInfo": {"name": "test-client", "version": "1.0"},
            },
        }}
        status, body = self._post_mcp(request, {
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
            "Mcp-Method": "resources/read", "Mcp-Name": "test://item",
        })
        self.assertEqual(status, 200)
        self.assertTrue(body["result"]["isError"])
        self.assertIn("unsupported ZChat resource URI", body["result"]["contents"][0]["text"])

    def test_legacy_get_returns_405(self):
        request = urllib.request.Request(self.endpoint, method="GET")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=10)
        self.assertEqual(caught.exception.code, 405)

    def test_delete_mcp_returns_405(self):
        request = urllib.request.Request(self.endpoint, method="DELETE")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=10)
        self.assertEqual(caught.exception.code, 405)

    def test_invalid_client_info_rejected(self):
        request = {"jsonrpc": "2.0", "id": 75, "method": "tools/list", "params": {"_meta": {
            "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL_VERSION,
            "io.modelcontextprotocol/clientCapabilities": {},
            "io.modelcontextprotocol/clientInfo": "invalid",
        }}}
        status, body = self._post_mcp(request, {
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
            "Mcp-Method": "tools/list",
        })
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], -32602)

    def test_submit_and_get_task(self):
        created=self.client.call_tool("workforce.submit_task",{"agent_id":"researcher","prompt":"MCP task"})
        task_id=created["structuredContent"]["task"]["id"]
        self.engine.worker_loop("mcp-worker",once=True)
        result=self.client.call_tool("workforce.get_task",{"task_id":task_id})
        self.assertEqual(result["structuredContent"]["status"],"succeeded")
    def test_install_prometa_tool(self):
        result=self.client.call_tool("workforce.install_prometa",{})
        self.assertEqual(result["structuredContent"]["agents"],28)
        self.assertEqual(result["structuredContent"]["skills"],22)
        self.assertTrue(self.db.get_agent("default","incident-commander"))
        self.assertTrue(self.db.get_workflow("default","prometa-incident-response"))

if __name__=="__main__": unittest.main()
