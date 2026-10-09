import json
import urllib.error
import urllib.request
import threading
import unittest
from http.server import ThreadingHTTPServer

from common import stack
from zworkforce.api import App
from zworkforce.mcp import RemoteMCPClient, MCP_PROTOCOL_VERSION


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
        self.assertIn("_meta", discovery)
        tools = self.client.list_tools()["tools"]
        self.assertTrue(any(x["name"] == "workforce.submit_task" for x in tools))
        self.assertTrue(any(x["name"] == "workforce.install_prometa" for x in tools))

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
        self.assertEqual(body["error"]["code"], -32022)

    def test_version_mismatch_returns_jsonrpc_error(self):
        request = {"jsonrpc": "2.0", "id": 50, "method": "tools/list", "params": {"_meta": {
            "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL_VERSION,
            "io.modelcontextprotocol/clientCapabilities": {},
        }}}
        status, body = self._post_mcp(request, {
            "MCP-Protocol-Version": "2025-11-25",
            "Mcp-Method": "tools/list",
        })
        self.assertEqual(status, 400)
        self.assertEqual(body["id"], 50)
        self.assertEqual(body["error"]["code"], -32020)

    def test_modern_method_header_mismatch_rejected(self):
        request = {"jsonrpc": "2.0", "id": 51, "method": "tools/list", "params": {"_meta": {
            "io.modelcontextprotocol/protocolVersion": MCP_PROTOCOL_VERSION,
            "io.modelcontextprotocol/clientCapabilities": {},
        }}}
        status, body = self._post_mcp(request, {
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
            "Mcp-Method": "tools/call",
        })
        self.assertEqual(status, 400)
        self.assertEqual(body["id"], 51)
        self.assertEqual(body["error"]["code"], -32020)

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
