"""Unit, contract, and workflow tests for ZEAZVERSE Idol Studio."""

from __future__ import annotations

import json
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from tests.common import stack
from zworkforce.api import App
from zworkforce.zeazverse_bibles import CANONICAL_CHARACTERS, ZEAZVERSE_BRAND
from zworkforce.zeazverse_domain import (
    ZeazverseValidationError,
    evaluate_qa_continuity,
    generate_cinematic_storyboard,
    generate_youtube_seo_metadata,
    validate_character_data,
    validate_episode_data,
    validate_series_data,
)
from zworkforce.zeazverse_adapters import VideoEditingPipeline


class ZeazverseDomainTest(unittest.TestCase):
    def test_canonical_characters_exist_and_adult(self):
        self.assertEqual(len(CANONICAL_CHARACTERS), 4)
        for cid in ["lalin", "nicha", "pim", "yada"]:
            self.assertIn(cid, CANONICAL_CHARACTERS)
            char = CANONICAL_CHARACTERS[cid]
            self.assertGreaterEqual(char["age"], 21)
            self.assertEqual(char["nationality"], "Thai")
            self.assertIn("appearance", char)
            self.assertIn("costume", char)
            self.assertIn("personality", char)
            self.assertIn("story_themes", char)

    def test_character_validation_rejects_underage(self):
        invalid_char = {"id": "minor_char", "name": "Minor", "age": 19, "nationality": "Thai"}
        with self.assertRaises(ZeazverseValidationError):
            validate_character_data(invalid_char)

    def test_cinematic_storyboard_generation(self):
        ep = {"id": "ep_test", "title": "Dawn of Bangkok 2088", "content_class": "Cyberpunk Stories"}
        scenes = generate_cinematic_storyboard(ep, [CANONICAL_CHARACTERS["lalin"]])
        self.assertEqual(len(scenes), 5)
        # Check time continuity
        self.assertEqual(scenes[0]["time_start_seconds"], 0.0)
        self.assertEqual(scenes[4]["time_end_seconds"], 30.0)
        # Check scene prompt contract
        for s in scenes:
            self.assertTrue(len(s["positive_prompt"]) > 10)
            self.assertTrue(len(s["negative_prompt"]) > 10)
            self.assertEqual(s["generation_model"], "mock-video-v1")
            self.assertIn("character_ref_ids", s)

    def test_youtube_seo_and_disclosure(self):
        ep = {"id": "ep_01", "title": "Cyber Mirage"}
        seo = generate_youtube_seo_metadata(ep, [CANONICAL_CHARACTERS["lalin"]])
        self.assertEqual(seo["privacy_status"], "private")
        self.assertTrue(seo["contains_synthetic_media"])
        self.assertFalse(seo["self_declared_made_for_kids"])
        self.assertIn("Synthetic Media Disclosure", seo["description"])
        self.assertIn("#ZEAZVERSE", seo["description"])

    def test_video_render_and_media_qa(self):
        pipeline = VideoEditingPipeline(output_dir="/tmp/zeazverse_test_renders")
        ep = {"id": "ep_render_test"}
        scenes = generate_cinematic_storyboard(ep, [CANONICAL_CHARACTERS["nicha"]])
        render_res = pipeline.render_episode("ep_render_test", scenes, {})
        self.assertEqual(render_res["status"], "completed")
        self.assertEqual(render_res["format"], "1080x1920")
        self.assertEqual(render_res["fps"], 30)

        qa = evaluate_qa_continuity(scenes, render_res)
        self.assertEqual(qa["passed"], 1)
        self.assertGreater(qa["identity_consistency_score"], 0.9)


class ZeazverseApiIntegrationTest(unittest.TestCase):
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

    def _req(self, method: str, path: str, body: dict | None = None, extra_headers: dict | None = None):
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        h = dict(self.headers)
        if extra_headers:
            h.update(extra_headers)
        req = urllib.request.Request(url, data=data, headers=h, method=method)
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_get_brand_and_characters(self):
        status, data = self._req("GET", "/api/v1/zeazverse/brand")
        self.assertEqual(status, 200)
        self.assertEqual(data["brand"]["name"], "ZEAZVERSE")

        status, data = self._req("GET", "/api/v1/zeazverse/characters")
        self.assertEqual(status, 200)
        names = [c["name"] for c in data["characters"]]
        self.assertIn("LALIN", names)
        self.assertIn("NICHA", names)
        self.assertIn("PIM", names)
        self.assertIn("YADA", names)

    def test_channel_setup_step_progression(self):
        status, data = self._req(
            "POST",
            "/api/v1/zeazverse/channel/setup-step",
            body={"step_id": "step_01", "status": "verified", "notes": "Admin MFA active"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["updated_step"], "step_01")
        self.assertEqual(data["status"], "verified")

    def test_end_to_end_episode_lifecycle(self):
        # 1. Create series
        status, s_data = self._req(
            "POST",
            "/api/v1/zeazverse/series",
            body={"id": "cyber-bangkok", "title": "Cyber Bangkok 2088", "content_class": "Cyberpunk Stories"},
        )
        self.assertEqual(status, 201)

        # 2. Create episode
        ep_id = "ep-pilots-01"
        status, ep_data = self._req(
            "POST",
            "/api/v1/zeazverse/episodes",
            body={
                "id": ep_id,
                "series_id": "cyber-bangkok",
                "title": "Awakening of LALIN",
                "content_class": "Cyberpunk Stories",
                "characters": ["lalin"],
            },
            extra_headers={"Idempotency-Key": "idem-ep-01"},
        )
        self.assertEqual(status, 201)
        self.assertEqual(ep_data["episode"]["status"], "IDEA")

        # 3. Generate Storyboard
        status, sb_data = self._req("POST", f"/api/v1/zeazverse/episodes/{ep_id}/generate-storyboard")
        self.assertEqual(status, 200)
        self.assertEqual(len(sb_data["scenes"]), 5)
        self.assertEqual(sb_data["status"], "SCRIPT_APPROVED")

        # 4. Generate SEO Metadata
        status, seo_data = self._req("POST", f"/api/v1/zeazverse/episodes/{ep_id}/generate-seo")
        self.assertEqual(status, 200)
        self.assertEqual(seo_data["seo_metadata"]["privacy_status"], "private")

        # 5. Render & Technical QA
        status, render_data = self._req("POST", f"/api/v1/zeazverse/episodes/{ep_id}/render")
        self.assertEqual(status, 200)
        self.assertEqual(render_data["status"], "QA_PASSED")

        # 6. Request Publishing Approval
        status, req_data = self._req(
            "POST",
            f"/api/v1/zeazverse/episodes/{ep_id}/request-approval",
            body={"target_visibility": "private"},
            extra_headers={"Idempotency-Key": "idem-req-01"},
        )
        self.assertEqual(status, 201)
        approval_id = req_data["approval_request"]["id"]

        # 7. Approve (Human in the Loop)
        status, dec_data = self._req(
            "POST",
            "/api/v1/zeazverse/approvals/decide",
            body={"request_id": approval_id, "approved": True, "comment": "Verified compliance"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(dec_data["approval"]["state"], "approved")

        # 8. YouTube Private Publishing with approved single-use token
        status, pub_data = self._req(
            "POST",
            f"/api/v1/zeazverse/episodes/{ep_id}/publish",
            body={"approval_id": approval_id},
            extra_headers={"Idempotency-Key": "idem-pub-01"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(pub_data["status"], "PRIVATE_UPLOADED")
        self.assertEqual(pub_data["visibility"], "private")

        # 9. Verify approval cannot be reused (consume-once)
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._req(
                "POST",
                f"/api/v1/zeazverse/episodes/{ep_id}/publish",
                body={"approval_id": approval_id},
                extra_headers={"Idempotency-Key": "idem-pub-02"},
            )
        self.assertEqual(ctx.exception.code, 400)
