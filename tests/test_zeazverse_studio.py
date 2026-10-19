"""Unit, contract, and workflow tests for ZEAZVERSE Idol Studio."""

from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import tempfile
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

    def test_storyboard_uses_only_selected_episode_characters(self):
        scenes = generate_cinematic_storyboard({"id": "ep_pim", "title": "PIM Pilot"}, [CANONICAL_CHARACTERS["pim"]])
        self.assertTrue(all(scene["characters"] == ["pim"] for scene in scenes))

    def test_youtube_seo_and_disclosure(self):
        ep = {"id": "ep_01", "title": "Cyber Mirage"}
        seo = generate_youtube_seo_metadata(ep, [CANONICAL_CHARACTERS["lalin"]])
        self.assertEqual(seo["privacy_status"], "private")
        self.assertTrue(seo["contains_synthetic_media"])
        self.assertFalse(seo["self_declared_made_for_kids"])
        self.assertIn("Synthetic Media Disclosure", seo["description"])
        self.assertIn("#ZEAZVERSE", seo["description"])

    def test_video_render_and_media_qa(self):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("FFmpeg and ffprobe are required for media validation")
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        pipeline = VideoEditingPipeline(output_dir=temp.name)
        ep = {"id": "ep_render_test"}
        scenes = generate_cinematic_storyboard(ep, [CANONICAL_CHARACTERS["nicha"]])
        render_res = pipeline.render_episode("ep_render_test", scenes, {})
        self.assertEqual(render_res["status"], "synthetic_sample")
        self.assertFalse(render_res["external_media_generated"])
        self.assertEqual(render_res["format"], "720x1280")
        self.assertEqual(render_res["fps"], 30)
        media_path = render_res["output_video_uri"]
        self.assertGreater(__import__("pathlib").Path(media_path).stat().st_size, 1024)
        self.assertEqual(hashlib.sha256(__import__("pathlib").Path(media_path).read_bytes()).hexdigest(), render_res["output_sha256"])
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height", "-of", "json", media_path],
            check=True, capture_output=True, text=True,
        )
        streams = json.loads(probe.stdout)["streams"]
        self.assertTrue(any(s.get("codec_name") == "h264" and s.get("width") == 720 and s.get("height") == 1280 for s in streams))

        qa = evaluate_qa_continuity(scenes, render_res)
        self.assertTrue(qa["technical_checks_passed"])
        self.assertEqual(qa["visual_review_status"], "pending")
        self.assertTrue(qa["human_visual_review_required"])
        self.assertIn("--> ", __import__("pathlib").Path(render_res["subtitles_vtt_uri"]).read_text(encoding="utf-8"))


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
        lalin = next(c for c in data["characters"] if c["id"] == "lalin")
        self.assertTrue(lalin["costume_config"].get("accessories"))
        self.assertTrue(lalin["accessories"])
        self.assertTrue(lalin["reference_turnaround"]["views"])

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
                "story_concept": {"synopsis": "LALIN discovers a signal beneath Bangkok."},
            },
            extra_headers={"Idempotency-Key": "idem-ep-01"},
        )
        self.assertEqual(status, 201)
        self.assertEqual(ep_data["episode"]["status"], "IDEA")
        status, duplicate_episode = self._req(
            "POST", "/api/v1/zeazverse/episodes",
            body={"id": ep_id, "series_id": "cyber-bangkok", "title": "Changed duplicate", "content_class": "Cyberpunk Stories"},
            extra_headers={"Idempotency-Key": "idem-ep-01"},
        )
        self.assertEqual(status, 201)
        self.assertEqual(duplicate_episode["episode"]["title"], "Awakening of LALIN")
        status, listed = self._req("GET", "/api/v1/zeazverse/episodes?series_id=cyber-bangkok&limit=1")
        self.assertEqual(status, 200)
        self.assertEqual(listed["episodes"][0]["story_concept"]["synopsis"], "LALIN discovers a signal beneath Bangkok.")

        # 3. Generate Storyboard
        status, sb_data = self._req("POST", f"/api/v1/zeazverse/episodes/{ep_id}/generate-storyboard")
        self.assertEqual(status, 200)
        self.assertEqual(len(sb_data["scenes"]), 5)
        self.assertEqual(sb_data["status"], "SCRIPT_APPROVED")
        self.assertEqual(sb_data["scenes"][0]["characters"], ["lalin"])
        self.assertEqual(sb_data["scenes"][3]["characters"], ["lalin"])

        # 4. Generate SEO Metadata
        status, seo_data = self._req("POST", f"/api/v1/zeazverse/episodes/{ep_id}/generate-seo")
        self.assertEqual(status, 200)
        self.assertEqual(seo_data["seo_metadata"]["privacy_status"], "private")
        self.assertIn("LALIN discovers a signal beneath Bangkok.", seo_data["seo_metadata"]["description"])

        # 5. Render & Technical QA
        status, render_data = self._req("POST", f"/api/v1/zeazverse/episodes/{ep_id}/render")
        self.assertEqual(status, 200)
        self.assertEqual(render_data["status"], "QA_PENDING")
        self.assertTrue(render_data["qa_report"]["human_visual_review_required"])
        video_artifact_id = render_data["render_result"]["video_artifact"]["id"]
        _, content_data = self._req("GET", f"/api/v1/artifacts/{video_artifact_id}/content")
        import base64
        media_bytes = base64.b64decode(content_data["content_base64"], validate=True)
        self.assertEqual(hashlib.sha256(media_bytes).hexdigest(), content_data["sha256"])

        # Visual review is an explicit human action; technical rendering alone cannot approve release.
        status, qa_data = self._req(
            "POST", f"/api/v1/zeazverse/episodes/{ep_id}/qa-review",
            body={"visual_review_passed": True, "notes": "Reviewed rendered storyboard sample"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(qa_data["status"], "QA_PASSED")

        # 6. Request Publishing Approval
        status, req_data = self._req(
            "POST",
            f"/api/v1/zeazverse/episodes/{ep_id}/request-approval",
            body={"target_visibility": "private"},
            extra_headers={"Idempotency-Key": "idem-req-01"},
        )
        self.assertEqual(status, 201)
        approval_id = req_data["approval_request"]["id"]
        _, duplicate_approval = self._req(
            "POST", f"/api/v1/zeazverse/episodes/{ep_id}/request-approval",
            body={"target_visibility": "private"}, extra_headers={"Idempotency-Key": "idem-req-01"},
        )
        self.assertEqual(duplicate_approval["approval_request"]["id"], approval_id)

        # 7. A distinct reviewer approves (self-approval is rejected).
        with self.assertRaises(urllib.error.HTTPError) as self_approval:
            self._req("POST", "/api/v1/zeazverse/approvals/decide",
                      body={"request_id": approval_id, "approved": True})
        self.assertEqual(self_approval.exception.code, 400)
        self_approval.exception.close()
        _, reviewer_secret = self.app.auth.create_key("default", "zeazverse-reviewer", "admin", ["*"])
        status, dec_data = self._req(
            "POST",
            "/api/v1/zeazverse/approvals/decide",
            body={"request_id": approval_id, "approved": True, "comment": "Verified compliance"},
            extra_headers={"Authorization": f"Bearer {reviewer_secret}"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(dec_data["approval"]["state"], "approved")

        # 8. Publishing must fail closed without consuming the approval or inventing a YouTube ID.
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._req(
                "POST",
                f"/api/v1/zeazverse/episodes/{ep_id}/publish",
                body={"approval_id": approval_id},
                extra_headers={"Idempotency-Key": "idem-pub-01"},
            )
        self.assertEqual(ctx.exception.code, 503)
        ctx.exception.close()
        with self.assertRaises(urllib.error.HTTPError) as locked_edit:
            self._req("POST", f"/api/v1/zeazverse/episodes/{ep_id}/generate-storyboard")
        self.assertEqual(locked_edit.exception.code, 400)
        locked_edit.exception.close()
        with self.db.connection() as conn:
            conn.execute("UPDATE zeazverse_scenes SET subject_action=? WHERE tenant_id=? AND episode_id=? AND id=?",
                         ("Changed after approval", "default", ep_id, "scene_01_hook"))
        with self.assertRaises(urllib.error.HTTPError) as stale_publish:
            self._req("POST", f"/api/v1/zeazverse/episodes/{ep_id}/publish", body={"approval_id": approval_id})
        self.assertEqual(stale_publish.exception.code, 400)
        stale_publish.exception.close()
        with self.db.connection() as conn:
            approval = conn.execute(
                "SELECT consumed_at FROM zeazverse_approval_requests WHERE tenant_id=? AND id=?",
                ("default", approval_id),
            ).fetchone()
        self.assertIsNone(approval["consumed_at"])
        self.assertTrue(self.db.verify_audit_chain("default")["ok"])
        actions = {item["action"] for item in self.db.list_audit("default", limit=1000)}
        self.assertIn("zeazverse.qa.review", actions)
        self.assertIn("zeazverse.approval.decide", actions)
        self.assertIn("zeazverse.publish.attempt", actions)
