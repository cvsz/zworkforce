import hashlib
import hmac
import json
import os
import threading
import unittest
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

from common import stack
from zworkforce import __version__
from zworkforce.api import App, _sanitize_header_value


class ApiV2Tests(unittest.TestCase):
    def setUp(self):
        self._previous_github_webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
        os.environ["GITHUB_WEBHOOK_SECRET"] = "test-secret"
        self.temp,self.settings,self.db,self.provider,self.engine,self.auth=stack()
        self.app=App(self.settings,self.db,self.engine,self.auth,self.provider)
        self.server=ThreadingHTTPServer(("127.0.0.1",0),self.app.handler())
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.base=f"http://127.0.0.1:{self.server.server_address[1]}"
    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.engine.shutdown(); self.temp.cleanup()
        if self._previous_github_webhook_secret is None:
            os.environ.pop("GITHUB_WEBHOOK_SECRET", None)
        else:
            os.environ["GITHUB_WEBHOOK_SECRET"] = self._previous_github_webhook_secret
    def req(self,path,method="GET",body=None,headers=None,timeout=15):
        h={"Authorization":"Bearer test-admin-secret",**(headers or {})}
        data=None
        if body is not None:
            data=json.dumps(body).encode(); h["Content-Type"]="application/json"
        r=urllib.request.Request(self.base+path,data=data,headers=h,method=method)
        with urllib.request.urlopen(r,timeout=timeout) as resp:
            return resp.status,dict(resp.headers),json.loads(resp.read())
    def test_health_is_public(self):
        with urllib.request.urlopen(self.base+"/health",timeout=5) as r:
            data=json.loads(r.read())
            self.assertEqual(data["version"],__version__)
            self.assertEqual(r.headers["X-Frame-Options"],"DENY")

    def test_header_values_strip_response_splitting_bytes(self):
        self.assertEqual(_sanitize_header_value("request\r\nInjected: yes"), "requestInjected: yes")
        self.assertEqual(_sanitize_header_value("origin\nInjected: yes"), "originInjected: yes")

    def test_static_asset_uses_explicit_content_type(self):
        req=urllib.request.Request(self.base+"/app.js")
        with urllib.request.urlopen(req,timeout=5) as r:
            self.assertEqual(r.headers["Content-Type"], "text/javascript; charset=utf-8")
    def test_overview_auth_and_task_dispatch(self):
        status,headers,data=self.req("/api/v1/overview")
        self.assertEqual(status,200); self.assertIn("credits_24h",data)
        status,_,task=self.req("/api/v1/tasks","POST",{"agent_id":"researcher","prompt":"summarize this"})
        self.assertEqual(status,201)
        self.engine.worker_loop("api-test",once=True)
        _,_,done=self.req("/api/v1/tasks/"+task["id"])
        self.assertEqual(done["status"],"succeeded")
    def test_scheduler_tick_endpoint_runs_once(self):
        status,_,data=self.req("/api/v1/scheduler-tick","POST",{})
        self.assertEqual(status,200)
        self.assertEqual(data["ticks"],1)
    def test_superadmin_tenant_switch(self):
        self.req("/api/v1/tenants","POST",{"id":"acme","name":"Acme"})
        _,_,data=self.req("/api/v1/agents",headers={"X-Tenant-ID":"acme"})
        self.assertEqual(len(data["items"]),6)
    def test_prometa_install_endpoint_installs_full_catalog(self):
        status,_,data=self.req("/api/v1/prometa/install","POST",{})
        self.assertEqual(status,201)
        self.assertEqual(data["agents"],28)
        self.assertEqual(data["skills"],22)
        self.assertEqual(data["agent_templates"],3)
        self.assertEqual(data["workflows"],4)
        _,_,agents=self.req("/api/v1/agents")
        self.assertTrue(any(item["id"]=="incident-commander" for item in agents["items"]))
        _,_,skills=self.req("/api/v1/skills")
        self.assertTrue(any(item["id"]=="release-verification" for item in skills["items"]))
    def test_tool_events_require_admin_role(self):
        _,secret=self.auth.create_key("default","viewer","viewer",["workforce:read","audit:read"])
        req=urllib.request.Request(self.base+"/api/v1/tool-events",headers={"Authorization":"Bearer "+secret})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req,timeout=5)
        self.assertEqual(ctx.exception.code,403)
    def test_static_assets_contain_slash_command_autocomplete(self):
        req_html = urllib.request.Request(self.base + "/")
        with urllib.request.urlopen(req_html, timeout=5) as r:
            html = r.read().decode("utf-8")
            self.assertIn('id="slashMenu"', html)
            self.assertIn('class="slash-menu hidden"', html)
            self.assertIn('id="slashHint"', html)

        req_js = urllib.request.Request(self.base + "/app.js")
        with urllib.request.urlopen(req_js, timeout=5) as r:
            js = r.read().decode("utf-8")
            self.assertIn('/api/v1/workspaces/commands', js)
            self.assertIn('updateSlashMenu', js)
            self.assertIn('selectSlashCommand', js)
            self.assertIn('/api/v1/workspaces/commands/resolve', js)

        req_css = urllib.request.Request(self.base + "/styles.css")
        with urllib.request.urlopen(req_css, timeout=5) as r:
            css = r.read().decode("utf-8")
            self.assertIn('.slash-menu', css)
            self.assertIn('.slash-item', css)
            self.assertIn('.slash-hint', css)

    def test_missing_auth_is_401(self):
        req = urllib.request.Request(self.base + "/api/v1/overview")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 401)


    def webhook_req(self, path, body, signature):
        headers = {
            "Content-Type": "application/json",
            "X-GitHub-Event": "check_run",
            "X-GitHub-Delivery": "51e66fb4-baf5-11f1-8ef7-9a4a53b184e9",
            "X-Hub-Signature-256": signature,
        }
        req = urllib.request.Request(self.base + path, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, dict(resp.headers), json.loads(resp.read())

    def test_github_webhook_public_and_canonical_paths_accept_signed_delivery(self):
        body = json.dumps({
            "action": "completed",
            "repository": {"full_name": "cvsz/zworkforce"},
        }).encode("utf-8")
        signature = "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
        for path in ("/github/webhook", "/webhooks/github"):
            status, headers, payload = self.webhook_req(path, body, signature)
            self.assertEqual(status, 200)
            self.assertEqual(payload["status"], "accepted")
            self.assertEqual(payload["event"], "check_run")
            self.assertEqual(payload["delivery"], "51e66fb4-baf5-11f1-8ef7-9a4a53b184e9")
            self.assertEqual(payload["repository"], "cvsz/zworkforce")
            self.assertEqual(headers["X-GitHub-Delivery"], payload["delivery"])

    def test_github_webhook_rejects_bad_signature_instead_of_404(self):
        body = b"{}"
        req = urllib.request.Request(
            self.base + "/github/webhook",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "check_run",
                "X-GitHub-Delivery": "delivery-123",
                "X-Hub-Signature-256": "sha256=deadbeef",
            },
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 401)

    def test_github_webhook_fails_closed_without_secret(self):
        os.environ.pop("GITHUB_WEBHOOK_SECRET", None)
        body = b"{}"
        req = urllib.request.Request(
            self.base + "/github/webhook",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "check_run",
                "X-GitHub-Delivery": "delivery-123",
                "X-Hub-Signature-256": "sha256=deadbeef",
            },
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 503)
        os.environ["GITHUB_WEBHOOK_SECRET"] = "test-secret"


if __name__ == "__main__":
    unittest.main()


