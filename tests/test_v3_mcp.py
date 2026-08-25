import json
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
        discovery=self.client.discover();self.assertEqual(discovery["protocolVersion"],MCP_PROTOCOL_VERSION)
        tools=self.client.list_tools()["tools"];self.assertTrue(any(x["name"]=="workforce.submit_task" for x in tools))
        self.assertTrue(any(x["name"]=="workforce.install_prometa" for x in tools))
    def test_standard_initialize_handshake(self):
        initialized=self.client.request("initialize",{"clientInfo":{"name":"codex","version":"test"}})
        self.assertEqual(initialized["protocolVersion"],MCP_PROTOCOL_VERSION)
        self.assertEqual(initialized["serverInfo"]["name"],"zworkforce")
        self.assertIn("tools",initialized["capabilities"])
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
