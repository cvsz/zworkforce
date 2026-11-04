import asyncio
import unittest
import base64
import sys
from pathlib import Path

ZIDER_ROOT = Path(__file__).resolve().parent.parent
if str(ZIDER_ROOT) not in sys.path:
    sys.path.insert(0, str(ZIDER_ROOT))

import warnings
warnings.filterwarnings("ignore", message=".*starlette.testclient.*")

from app.services.pdf_service import PDFService

try:
    from fastapi.testclient import TestClient
    from app.main import app
except ModuleNotFoundError:
    TestClient = None
    app = None


class TestZiderPDFTenantIsolationUnit(unittest.TestCase):
    def setUp(self):
        PDFService._docs.clear()

    def test_pdf_service_isolates_documents_by_tenant(self):
        doc_a = asyncio.run(
            PDFService.process_pdf(
                b"Confidential Tenant A Financial Forecast 2026",
                "forecast-a.pdf",
                tenant_id="tenant-a",
            )
        )
        self.assertEqual(doc_a["tenant_id"], "tenant-a")

        cross_tenant = asyncio.run(
            PDFService.query_doc(
                doc_id=doc_a["doc_id"],
                query="Forecast",
                model="gpt-4o-mini",
                tenant_id="tenant-b",
            )
        )
        self.assertIn("not found or expired", cross_tenant["answer"])

        same_tenant = asyncio.run(
            PDFService.query_doc(
                doc_id=doc_a["doc_id"],
                query="Forecast",
                model="gpt-4o-mini",
                tenant_id="tenant-a",
            )
        )
        self.assertIn("forecast-a.pdf", same_tenant["answer"])


@unittest.skipIf(TestClient is None, "fastapi is not installed in this environment")
class TestZiderAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_check(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "zider-bff")

    def test_write_endpoint(self):
        resp = self.client.post("/api/write", json={
            "action": "improve",
            "text": "Hello world this is test",
            "tone": "professional"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("result", data)
        self.assertEqual(data["action"], "improve")

    def test_translate_endpoint(self):
        resp = self.client.post("/api/translate", json={
            "text": "Hello world",
            "source_lang": "en",
            "target_lang": "es"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("translated_text", data)

    def test_batch_translate_endpoint(self):
        resp = self.client.post("/api/translate/batch", json={
            "items": ["Title text", "Paragraph description"],
            "source_lang": "en",
            "target_lang": "es"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["items"]), 2)

    def test_summarize_endpoint(self):
        resp = self.client.post("/api/summarize/webpage", json={
            "raw_text": "This is a detailed paragraph discussing modern browser extensions and AI sidebars."
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("summary", data)

    def test_summarize_endpoint_rejects_ssrf_and_private_addresses(self):
        resp = self.client.post("/api/summarize/webpage", json={
            "url": "http://localhost:8080/internal-secrets"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("Could not fetch", data["summary"])

        resp2 = self.client.post("/api/summarize/webpage", json={
            "url": "http://127.0.0.1:9569/api/v1/overview"
        })
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertIn("Could not fetch", data2["summary"])

        resp3 = self.client.post("/api/summarize/webpage", json={
            "url": "file:///etc/passwd"
        })
        self.assertEqual(resp3.status_code, 200)
        data3 = resp3.json()
        self.assertIn("Could not fetch", data3["summary"])

    def test_search_endpoint(self):
        resp = self.client.post("/api/search", json={
            "query": "artificial intelligence latest trends",
            "max_results": 3
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("results", data)
        self.assertTrue(len(data["results"]) > 0)

    def test_prompts_endpoint(self):
        resp = self.client.get("/api/prompts")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(len(data) > 0)
        self.assertIn("template", data[0])

    def test_vision_analyze_endpoint(self):
        sample_b64 = base64.b64encode(b"fake_image_bytes").decode("utf-8")
        resp = self.client.post("/api/vision/analyze", json={
            "image_base64": f"data:image/png;base64,{sample_b64}",
            "prompt": "Extract text"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("analysis", data)

    def test_image_generate_endpoint(self):
        resp = self.client.post("/api/image/generate", json={
            "prompt": "Cyberpunk workspace with neon blue lights",
            "style": "photorealistic"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("image_url", data)

    def test_zworkforce_bridge_endpoints(self):
        resp = self.client.get("/api/zworkforce/overview")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("status", data)

        dispatch_resp = self.client.post("/api/zworkforce/dispatch", json={
            "title": "Analyze Data Task",
            "prompt": "Extract structured dataset",
            "target_agent": "general"
        })
        self.assertEqual(dispatch_resp.status_code, 200)
        dispatch_data = dispatch_resp.json()
        self.assertIn("task_id", dispatch_data)

    def test_agent_run_requires_explicit_structured_actions(self):
        resp = self.client.post("/api/agent/run", json={
            "goal": "Extract table headers from current view"
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("explicit structured actions", resp.json()["detail"])

    def test_agent_run_fails_closed_when_executor_is_unconfigured(self):
        resp = self.client.post("/api/agent/run", json={
            "goal": "Inspect the approved page",
            "actions": [{
                "kind": "inspect",
                "url": "https://example.com/"
            }]
        })
        self.assertEqual(resp.status_code, 503)
        self.assertIn("executor is not configured", resp.json()["detail"])

    def test_api_token_auth_and_tenant_pdf_isolation(self):
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {"ZIDER_API_TOKEN": "zider-secret-token", "ZIDER_REQUIRE_TENANT": "true"}):
            unauth = self.client.get("/api/prompts")
            self.assertEqual(unauth.status_code, 401)

            missing_tenant = self.client.get(
                "/api/prompts",
                headers={"Authorization": "Bearer zider-secret-token"},
            )
            self.assertEqual(missing_tenant.status_code, 403)

            invalid_tenant = self.client.get(
                "/api/prompts",
                headers={
                    "Authorization": "Bearer zider-secret-token",
                    "X-Tenant-ID": "../bad-tenant",
                },
            )
            self.assertEqual(invalid_tenant.status_code, 400)

            upload_a = self.client.post(
                "/api/pdf/upload",
                headers={
                    "Authorization": "Bearer zider-secret-token",
                    "X-Tenant-ID": "tenant-a",
                    "Content-Type": "application/json",
                },
                json={
                    "filename": "alpha.pdf",
                    "file_base64": base64.b64encode(b"Confidential alpha revenue report 2026").decode("utf-8"),
                },
            )
            self.assertEqual(upload_a.status_code, 200)
            doc_id = upload_a.json()["doc_id"]

            # Cross-tenant query must not find tenant-a's document
            cross_query = self.client.post(
                "/api/pdf/query",
                headers={
                    "Authorization": "Bearer zider-secret-token",
                    "X-Tenant-ID": "tenant-b",
                },
                json={"doc_id": doc_id, "query": "revenue", "model": "gpt-4o-mini"},
            )
            self.assertEqual(cross_query.status_code, 200)
            self.assertIn("not found or expired", cross_query.json()["answer"])

            # Same-tenant query succeeds
            same_query = self.client.post(
                "/api/pdf/query",
                headers={
                    "Authorization": "Bearer zider-secret-token",
                    "X-Tenant-ID": "tenant-a",
                },
                json={"doc_id": doc_id, "query": "revenue", "model": "gpt-4o-mini"},
            )
            self.assertEqual(same_query.status_code, 200)
            self.assertIn("alpha.pdf", same_query.json()["answer"])


if __name__ == "__main__":
    unittest.main()
