"""Unit and integration tests for the Universal Content Factory and Style Registry."""

from __future__ import annotations

import json
import threading
import unittest
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

from tests.common import stack
from zworkforce.api import App
from zworkforce.content_styles_data import CONTENT_STYLE_PRESETS


class ContentStylesRegistryTest(unittest.TestCase):
    def test_presets_total_and_categories(self):
        self.assertEqual(len(CONTENT_STYLE_PRESETS), 128)
        categories = set(p["category"] for p in CONTENT_STYLE_PRESETS)
        self.assertEqual(len(categories), 8)
        expected_cats = {
            "Kids & Family",
            "Animation & Fiction",
            "Cinematic & Storytelling",
            "Education & Knowledge",
            "Marketing & Business",
            "Social & Entertainment",
            "Documentary & Information",
            "Creative & Experimental",
        }
        self.assertEqual(categories, expected_cats)
        for cat in expected_cats:
            cat_presets = [p for p in CONTENT_STYLE_PRESETS if p["category"] == cat]
            self.assertEqual(len(cat_presets), 16, f"Category {cat} should have exactly 16 presets")

    def test_preset_schema_completeness(self):
        required_fields = [
            "style_id",
            "category",
            "display_name",
            "description",
            "supported_content_types",
            "audience_profile",
            "age_rating",
            "default_aspect_ratio",
            "target_duration",
            "visual_style",
            "animation_style",
            "camera_language",
            "lighting_profile",
            "color_grading",
            "editing_pace",
            "narration_style",
            "music_profile",
            "subtitle_style",
            "thumbnail_style",
            "safety_policy",
            "publishing_targets",
            "provider_capabilities",
            "estimated_cost_class",
            "prompt_template_version",
            "active",
        ]
        for p in CONTENT_STYLE_PRESETS:
            for field in required_fields:
                self.assertIn(field, p, f"Missing field {field} in preset {p.get('style_id')}")


class ContentStylesApiIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp, cls.settings, cls.db, cls.provider, cls.engine, cls.auth = stack()
        cls.app = App(cls.settings, cls.db, cls.engine, cls.auth, cls.provider)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), cls.app.handler())
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.headers = {
            "Authorization": "Bearer test-admin-secret",
            "Content-Type": "application/json",
        }

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.temp.cleanup()

    def _req(self, method: str, path: str, body: dict | None = None):
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, headers=self.headers, method=method)
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_preset_seed_is_idempotent(self):
        tenant_id = "preset-seed-idempotency"
        first = self.db.seed_content_style_presets(tenant_id)
        second = self.db.seed_content_style_presets(tenant_id)
        self.assertEqual(first, 128)
        self.assertEqual(second, 0)
        self.assertEqual(len(self.db.list_content_style_presets(tenant_id)), 128)

    def test_list_all_presets_and_categories_api(self):
        status, data = self._req("GET", "/api/v1/content-styles/categories")
        self.assertEqual(status, 200)
        self.assertEqual(data["total_categories"], 8)
        self.assertEqual(data["total_presets"], 128)

        status, data = self._req("GET", "/api/v1/content-styles/presets")
        self.assertEqual(status, 200)
        self.assertEqual(data["total"], 128)

    def test_filter_presets_by_category(self):
        status, data = self._req("GET", "/api/v1/content-styles/presets?category=Kids+%26+Family")
        self.assertEqual(status, 200)
        self.assertEqual(data["total"], 16)
        for p in data["presets"]:
            self.assertEqual(p["category"], "Kids & Family")

    def test_get_single_preset(self):
        status, data = self._req("GET", "/api/v1/content-styles/presets/cinematic-storytelling:cyberpunk")
        self.assertEqual(status, 200)
        preset = data["preset"]
        self.assertEqual(preset["display_name"], "Cyberpunk")
        self.assertEqual(preset["category"], "Cinematic & Storytelling")

    def test_missing_style_returns_structured_404(self):
        req = urllib.request.Request(
            f"{self.base_url}/api/v1/content-styles/presets/missing-style",
            headers=self.headers,
        )
        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(req)
        self.assertEqual(raised.exception.code, 404)
        payload = json.loads(raised.exception.read().decode("utf-8"))
        self.assertEqual(payload["error"]["code"], "preset_not_found")

    def test_create_creative_brief_with_style(self):
        body = {
            "id": "brief-neon-city-01",
            "style_id": "cinematic-storytelling:cyberpunk",
            "title": "Neon Awakening",
            "objective": "Introduce the future landscape",
        }
        status, data = self._req("POST", "/api/v1/content-styles/creative-briefs", body=body)
        self.assertEqual(status, 201)
        self.assertEqual(data["creative_brief"]["id"], "brief-neon-city-01")
        self.assertEqual(data["applied_style"]["display_name"], "Cyberpunk")
