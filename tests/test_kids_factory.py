from __future__ import annotations

import json
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from common import stack
from zworkforce.api import App
from zworkforce.kids_factory import (
    KidsValidationError,
    build_storyboard,
    kids_safety_check,
    prepare_youtube_metadata,
    mock_youtube_upload,
    storyboard_to_timeline,
    validate_brand,
    validate_character,
    validate_episode,
    validate_media_upload,
    validate_scene,
)


class KidsDomainTests(unittest.TestCase):
    def test_brand_validation_and_copyright_block(self):
        ok = validate_brand({"name": "LumiKids", "language": "en", "age_range": "3-6"})
        self.assertEqual(ok["name"], "LumiKids")
        with self.assertRaises(KidsValidationError):
            validate_brand({"name": "Cocomelon Clone"})
        with self.assertRaises(KidsValidationError):
            validate_brand({"name": "x", "language": "xx"})
        with self.assertRaises(KidsValidationError):
            validate_brand({"name": "Brand api_key=sk_1234567890123456"})

    def test_character_episode_scene_validation(self):
        validate_character({"name": "Lumi the Bus", "species": "bus"})
        with self.assertRaises(KidsValidationError):
            validate_character({"name": "Baby Shark Friend"})
        validate_episode({"title": "The Colorful Learning Bus", "age_band": "preschool", "language": "en"})
        with self.assertRaises(KidsValidationError):
            validate_episode({"title": "Bad", "age_band": "adult"})
        with self.assertRaises(KidsValidationError):
            validate_scene({"visual_prompt": "", "duration_seconds": 5})
        with self.assertRaises(KidsValidationError):
            validate_media_upload(filename="../evil.png", content_type="image/png", size_bytes=10)
        with self.assertRaises(KidsValidationError):
            validate_media_upload(filename="https://evil/x.png", content_type="image/png", size_bytes=10)
        with self.assertRaises(KidsValidationError):
            validate_media_upload(filename="clip.mp4", content_type="image/png", size_bytes=10)

    def test_safety_blocks_dangerous_and_ip(self):
        blocked = kids_safety_check(age_band="preschool", text="let us play with fire together")
        self.assertFalse(blocked["passed"])
        blocked_ip = kids_safety_check(age_band="2-4", text="meet Peppa Pig today")
        self.assertFalse(blocked_ip["passed"])
        clean = kids_safety_check(age_band="2-4", text="learn five colors with friends")
        self.assertTrue(clean["passed"])
        self.assertIn("simple_vocabulary", [c["item"] for c in clean["checklist"]])

    def test_storyboard_and_timeline_deterministic(self):
        plan = build_storyboard(script_body={"verses": "red blue", "chorus": "colors"}, num_scenes=3)
        self.assertEqual(len(plan), 3)
        self.assertEqual(plan[0]["ordering"], 0)
        tracks = storyboard_to_timeline([{"id": "s01", "ordering": 0, "duration_seconds": 5,
                                          "captions": [{"text": "hi"}], "music_cues": [{"cue": "x"}],
                                          "dialogue": {"line": "hello"}}], brand_name="LumiKids")
        self.assertIn("video", tracks)
        self.assertEqual(len(tracks["branding"]), 1)

    def test_youtube_metadata_never_defaults_false(self):
        meta = prepare_youtube_metadata(title="Colors", description="learn", audience="madeForKids")
        self.assertEqual(meta["audience"], "madeForKids")
        with self.assertRaises(KidsValidationError):
            prepare_youtube_metadata(title="", description="x")
        first = mock_youtube_upload(metadata=meta, idempotency_key="k1", sha256="abc")
        second = mock_youtube_upload(metadata=meta, idempotency_key="k1", sha256="abc")
        self.assertEqual(first["external_id"], second["external_id"])


class KidsPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp, self.settings, self.db, self.provider, self.engine, self.auth = stack()

    def tearDown(self):
        self.engine.shutdown()
        self.temp.cleanup()

    def test_brand_character_episode_versioning_and_tenant_isolation(self):
        db = self.db
        db.kids_upsert_brand("default", "lumikids", validate_brand({"name": "LumiKids", "language": "en"}), "tester")
        v1 = db.kids_get_brand("default", "lumikids")
        self.assertEqual(v1["version"], 1)
        db.kids_upsert_brand("default", "lumikids", validate_brand({"name": "LumiKids v2", "language": "en"}), "tester")
        self.assertEqual(db.kids_get_brand("default", "lumikids")["version"], 2)
        # แบรนด์เดิมต้องไม่รั่วข้าม tenant
        self.assertIsNone(db.kids_get_brand("other", "lumikids"))
        db.ensure_tenant("other", "Other")
        db.kids_upsert_brand("other", "lumikids", validate_brand({"name": "Other Brand", "language": "th"}), "tester")
        self.assertEqual(db.kids_get_brand("other", "lumikids")["name"], "Other Brand")
        self.assertEqual(db.kids_get_brand("default", "lumikids")["name"], "LumiKids v2")

        char = db.kids_upsert_character("default", "lumi", "lumikids", validate_character({"name": "Lumi"}), "tester")
        self.assertEqual(char["version"], 1)
        char2 = db.kids_upsert_character("default", "lumi", "lumikids", validate_character({"name": "Lumi Updated"}), "tester")
        self.assertEqual(char2["version"], 2)
        self.assertTrue(db.kids_lock_character("default", "lumi", "tester", locked=True))
        self.assertEqual(db.kids_get_character("default", "lumi")["locked"], 1)

    def test_episode_idempotency_and_approval_gated_publishing(self):
        db = self.db
        db.kids_upsert_brand("default", "lumikids", validate_brand({"name": "LumiKids", "language": "en"}), "t")
        ep, created = db.kids_create_episode("default", "bus-01", "lumikids",
                                             validate_episode({"title": "The Colorful Learning Bus"}), "t",
                                             idempotency_key="demo-1")
        self.assertTrue(created)
        ep2, created2 = db.kids_create_episode("default", "bus-01-dup", "lumikids",
                                               validate_episode({"title": "Dup"}), "t", idempotency_key="demo-1")
        self.assertFalse(created2)
        self.assertEqual(ep["id"], ep2["id"])

        script = db.kids_save_script("default", "bus-01", {"content_type": "nursery_rhyme", "body": {"verses": "red"}}, "t")
        self.assertEqual(script["version"], 1)
        db.kids_upsert_scene("default", "bus-01", "s01", validate_scene({"visual_prompt": "bus scene", "duration_seconds": 5}), "t")
        # เดียว scene regenerate ต้องไม่กระทบ scene อื่น
        db.kids_upsert_scene("default", "bus-01", "s02", validate_scene({"visual_prompt": "sky scene", "duration_seconds": 5}), "t")
        self.assertEqual(len(db.kids_list_scenes("default", "bus-01")), 2)
        db.kids_upsert_scene("default", "bus-01", "s01", validate_scene({"visual_prompt": "bus scene v2", "duration_seconds": 5}), "t")
        scenes = {s["id"]: s for s in db.kids_list_scenes("default", "bus-01")}
        self.assertIn("v2", scenes["s01"]["visual_prompt"])
        self.assertIn("sky", scenes["s02"]["visual_prompt"])

        timeline = db.kids_save_timeline("default", "bus-01", {"video": [], "captions": []}, "t")
        self.assertEqual(timeline["version"], 1)
        job, _ = db.kids_submit_render("default", "bus-01", 1, "landscape_1080p", "t", idempotency_key="r-1")
        job2, created_r = db.kids_submit_render("default", "bus-01", 1, "landscape_1080p", "t", idempotency_key="r-1")
        self.assertFalse(created_r)
        self.assertEqual(job["id"], job2["id"])

        approval = db.kids_request_approval("default", "bus-01", "episode", "bus-01", 1, "t")
        pub, _ = db.kids_prepare_publishing("default", "bus-01", {"title": "Colors", "approval_id": approval["id"]}, "t",
                                            idempotency_key="p-1")
        # ต้อง block เมื่อยังไม่มี approval
        with self.assertRaises(ValueError):
            db.kids_publish_approved("default", pub["id"], {"external_id": "x"}, "t")
        decided = db.kids_decide_approval("default", approval["id"], "approved", "reviewer", "good")
        self.assertEqual(decided["state"], "approved")
        done = db.kids_publish_approved("default", pub["id"], {"external_id": "mock-yt-abc"}, "t")
        self.assertEqual(done["status"], "published")
        # publish ซ้ำต้อง idempotent (คืนสถานะเดิม ไม่ duplicate)
        done2 = db.kids_publish_approved("default", pub["id"], {"external_id": "mock-yt-abc"}, "t")
        self.assertEqual(done2["status"], "published")


class KidsApiEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.temp, self.settings, self.db, self.provider, self.engine, self.auth = stack()
        self.app = App(self.settings, self.db, self.engine, self.auth, self.provider)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.app.handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.engine.shutdown()
        self.temp.cleanup()

    def req(self, path, method="GET", body=None, headers=None, secret="test-admin-secret"):
        h = {"Authorization": f"Bearer {secret}", **(headers or {})}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        r = urllib.request.Request(self.base + path, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(r, timeout=120) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")

    def test_full_demo_slice(self):
        # 1 brand
        s, brand = self.req("/api/v1/kids/brands", "POST", {"id": "lumikids", "name": "LumiKids", "language": "en",
                                                             "age_range": "3-6", "art_style": "soft pastel"})
        self.assertEqual(s, 201)
        # 2 character versioned
        s, char = self.req("/api/v1/kids/characters", "POST", {"id": "lumi", "brand_id": "lumikids", "name": "Lumi the Bus",
                                                                "species": "bus", "description": "friendly learning bus"})
        self.assertEqual(s, 201)
        # 3 episode
        s, ep = self.req("/api/v1/kids/episodes", "POST", {"id": "color-bus", "brand_id": "lumikids",
                                                           "title": "The Colorful Learning Bus", "summary": "Learn five colors",
                                                           "age_band": "preschool", "language": "en",
                                                           "objectives": ["five colors"], "vocabulary": ["red", "blue"]},
                         headers={"Idempotency-Key": "demo-e2e-1"})
        self.assertIn(s, (200, 201))
        # 4 structured script
        s, script = self.req(f"/api/v1/kids/episodes/{ep['id']}/script", "POST",
                             {"content_type": "nursery_rhyme",
                              "body": {"hook": "hi", "verses": "red bus", "chorus": "colors", "ending": "bye"}})
        self.assertEqual(s, 201)
        self.assertEqual(script["version"], 1)
        # 5 storyboard
        s, board = self.req(f"/api/v1/kids/episodes/{ep['id']}/storyboard", "POST", {"num_scenes": 3})
        self.assertEqual(s, 201)
        self.assertEqual(len(board["items"]), 3)
        # 6 asset attach
        s, asset = self.req("/api/v1/kids/assets", "POST", {"name": "s01.png", "content_type": "image/png",
                                                            "size_bytes": 12, "episode_id": ep["id"], "scene_id": "s01",
                                                            "storage_uri": "synthetic://mock", "sha256": "a" * 64})
        self.assertEqual(s, 201)
        # timeline
        s, timeline = self.req(f"/api/v1/kids/episodes/{ep['id']}/timeline", "POST", {})
        self.assertEqual(s, 201)
        self.assertTrue(timeline["checksum"])
        # 7 deterministic render
        s, render = self.req("/api/v1/kids/render-jobs", "POST", {"episode_id": ep["id"], "preset": "landscape_1080p"},
                             headers={"Idempotency-Key": "render-e2e-1"})
        self.assertEqual(s, 201)
        self.assertEqual(render["status"], "succeeded")
        self.assertTrue(render["output_sha256"])
        # 8 checksum present
        self.assertEqual(len(render["output_sha256"]), 64)
        # 9 approval request + 10 publishing blocked without approval
        s, approval = self.req("/api/v1/kids/approvals", "POST", {"episode_id": ep["id"], "subject_type": "episode"})
        self.assertEqual(s, 201)
        s, pub = self.req("/api/v1/kids/publishing/prepare", "POST",
                          {"episode_id": ep["id"], "title": "The Colorful Learning Bus",
                           "description": "Learn five colors", "audience": "madeForKids",
                           "approval_id": "pending-without-approval"},
                          headers={"Idempotency-Key": "pub-e2e-1"})
        self.assertEqual(s, 201)
        s, blocked = self.req(f"/api/v1/kids/publishing/{pub['id']}/publish", "POST", {})
        self.assertEqual(s, 400)
        # approve then 11 mock publish — four-eyes: requester cannot approve own request
        s, self_approved = self.req(f"/api/v1/kids/approvals/{approval['id']}/approve", "POST", {"comment": "self approve"})
        self.assertEqual(s, 400)
        _, reviewer_secret = self.auth.create_key("default", "human-reviewer", "admin", ["*"])
        s, decided = self.req(f"/api/v1/kids/approvals/{approval['id']}/approve", "POST", {"comment": "reviewer ok"},
                              secret=reviewer_secret)
        self.assertEqual(s, 200)
        # เตรียม job ใหม่ที่ผูก approval ที่อนุมัติแล้ว
        s, pub2 = self.req("/api/v1/kids/publishing/prepare", "POST",
                           {"episode_id": ep["id"], "title": "The Colorful Learning Bus",
                            "description": "Learn five colors", "audience": "madeForKids",
                            "approval_id": approval["id"]},
                           headers={"Idempotency-Key": "pub-e2e-2"})
        self.assertEqual(s, 201)
        s, published = self.req(f"/api/v1/kids/publishing/{pub2['id']}/publish", "POST", {})
        self.assertEqual(s, 200)
        self.assertEqual(published["status"], "published")
        # 12 audit captured
        s, audit = self.req("/api/v1/audit?limit=200")
        self.assertEqual(s, 200)
        kinds = {e["action"] for e in audit["items"]}
        self.assertTrue({"kids.brand.upsert", "kids.episode.create", "kids.render.submit",
                         "kids.approval.request", "kids.publishing.publish"} <= kinds)
        # overview reflects real backend state (never fabricated)
        s, overview = self.req("/api/v1/kids/overview")
        self.assertEqual(s, 200)
        self.assertGreaterEqual(overview["episodes"], 1)
        self.assertGreaterEqual(overview["published_videos"], 1)

    def test_cross_tenant_denied_and_secret_guard(self):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "lumikids", "name": "LumiKids", "language": "en"})
        self.assertEqual(s, 201)
        # ข้าม tenant ต้องไม่เห็น
        h = {"Authorization": "Bearer test-admin-secret", "X-Tenant-ID": "other"}
        s, data = self.req("/api/v1/kids/brands/lumikids", headers=h)
        self.assertEqual(s, 404)
        # secret ใน payload ต้องถูกปฏิเสธ
        s, data = self.req("/api/v1/kids/brands", "POST", {"id": "bad", "name": "x api_key=sk_1234567890123456"})
        self.assertEqual(s, 400)


class KidsCampaignPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp, self.settings, self.db, self.provider, self.engine, self.auth = stack()
        self.app = App(self.settings, self.db, self.engine, self.auth, self.provider)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.app.handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.engine.shutdown()
        self.temp.cleanup()

    def req(self, path, method="GET", body=None, headers=None):
        h = {"Authorization": "Bearer test-admin-secret", **(headers or {})}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        r = urllib.request.Request(self.base + path, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(r, timeout=60) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")

    def _seed_brand_episode(self, prefix="pp"):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": f"{prefix}-brand", "name": "Pipe Brand", "language": "en"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes", "POST", {"id": f"{prefix}-ep", "brand_id": f"{prefix}-brand",
                                                          "title": "Pipeline Episode", "summary": "learn colors",
                                                          "age_band": "preschool", "language": "en"})
        self.assertIn(s, (200, 201))

    def test_campaign_crud_and_tenant_isolation(self):
        self._seed_brand_episode("cp")
        s, campaign = self.req("/api/v1/kids/campaigns", "POST", {"id": "colors-q1", "brand_id": "cp-brand",
                                                                   "name": "Colors Q1", "topic": "five colors"})
        self.assertEqual(s, 201)
        s, listed = self.req("/api/v1/kids/campaigns?brand_id=cp-brand")
        self.assertEqual(s, 200)
        self.assertEqual(len(listed["items"]), 1)
        s, one = self.req("/api/v1/kids/campaigns/colors-q1")
        self.assertEqual(s, 200)
        h = {"Authorization": "Bearer test-admin-secret", "X-Tenant-ID": "other"}
        s, _ = self.req("/api/v1/kids/campaigns/colors-q1", headers=h)
        self.assertEqual(s, 404)

    def test_pipeline_runs_end_to_end_and_is_idempotent(self):
        self._seed_brand_episode("pl")
        s, first = self.req("/api/v1/kids/episodes/pl-ep/pipeline", "POST", {"num_scenes": 2})
        self.assertEqual(s, 200)
        self.assertEqual(first["failed"], "")
        self.assertIn("render", first["completed"])
        self.assertIn("approval_request", first["completed"])
        # rerun ต้อง skip งานที่เสร็จแล้ว ไม่ duplicate render/publishing
        s, second = self.req("/api/v1/kids/episodes/pl-ep/pipeline", "POST", {"num_scenes": 2})
        self.assertEqual(s, 200)
        self.assertEqual(second["failed"], "")
        s, runs = self.req("/api/v1/kids/agent-runs?episode_id=pl-ep")
        self.assertEqual(s, 200)
        steps = [r["step"] for r in runs["items"] if r["status"] == "succeeded"]
        for expected in ("research", "script", "storyboard", "assets", "timeline", "render", "qa", "approval_request"):
            self.assertIn(expected, steps)
        # render job ต้องมีแค่ job เดียวจาก pipeline idempotency (rerun ใช้ job เดิม)
        s, renders = self.req("/api/v1/kids/render-jobs?episode_id=pl-ep")
        self.assertEqual(s, 200)
        self.assertEqual(len(renders["items"]), 1)

    def test_pipeline_budget_gate_blocks_render(self):
        self._seed_brand_episode("bg")
        # ตั้ง budget ต่ำมากจน estimate เกิน → render ต้องถูก block พร้อม error ชัดเจน
        db = self.db
        with db.connection() as c:
            c.execute("UPDATE kids_episodes SET budget_credits=0.01 WHERE tenant_id='default' AND id='bg-ep'")
        s, result = self.req("/api/v1/kids/episodes/bg-ep/pipeline", "POST", {"num_scenes": 4})
        self.assertEqual(s, 200)
        self.assertEqual(result["failed"], "render")
        self.assertIn("budget", result["error"])
        s, renders = self.req("/api/v1/kids/render-jobs?episode_id=bg-ep")
        self.assertEqual(succeeds_or_empty(s, renders), True)

    def test_mcp_campaign_and_pipeline_tools(self):
        from zworkforce.mcp import _call_tool
        db = self.db
        db.ensure_tenant("default", "Default")
        db.kids_upsert_brand("default", "mcp-brand", validate_brand({"name": "MCP Brand", "language": "en"}), "t")
        # ใช้ fake principal ที่ผ่าน require จริง (superadmin + ทุก scope) ห้าม monkeypatch AuthManager
        principal = type("P", (), {"name": "tester", "role": "superadmin", "key_id": "k",
                                   "has_scope": lambda self, s: True})()
        created = _call_tool(self.app, principal, "default", "kids.create_campaign",
                             {"id": "mcp-camp", "brand_id": "mcp-brand", "name": "MCP Campaign"})
        self.assertEqual(created["id"], "mcp-camp")
        listed = _call_tool(self.app, principal, "default", "kids.list_campaigns", {})
        self.assertTrue(any(c["id"] == "mcp-camp" for c in listed["items"]))
        # mutating tool ต้องปฏิเสธ viewer ที่ไม่มี scope
        viewer = type("P", (), {"name": "v", "role": "viewer", "key_id": "k2",
                                "has_scope": lambda self, s: False})()
        with self.assertRaises(PermissionError):
            _call_tool(self.app, viewer, "default", "kids.create_campaign",
                       {"id": "nope", "brand_id": "mcp-brand", "name": "Nope"})


def succeeds_or_empty(status, renders):
    return status == 200 and len(renders["items"]) == 0


class KidsSlice3Tests(unittest.TestCase):
    def setUp(self):
        self.temp, self.settings, self.db, self.provider, self.engine, self.auth = stack()
        self.app = App(self.settings, self.db, self.engine, self.auth, self.provider)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.app.handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.engine.shutdown()
        self.temp.cleanup()

    def req(self, path, method="GET", body=None, headers=None):
        h = {"Authorization": "Bearer test-admin-secret", **(headers or {})}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        r = urllib.request.Request(self.base + path, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(r, timeout=60) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")

    def _seed_parent(self, prefix="sh"):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": f"{prefix}-brand", "name": "Shorts Brand", "language": "en"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes", "POST", {"id": f"{prefix}-ep", "brand_id": f"{prefix}-brand",
                                                          "title": "Long Episode", "summary": "learn colors and numbers",
                                                          "age_band": "preschool", "language": "en",
                                                          "objectives": ["colors"], "vocabulary": ["red"]})
        self.assertIn(s, (200, 201))
        s, _ = self.req(f"/api/v1/kids/episodes/{prefix}-ep/storyboard", "POST", {"num_scenes": 4})
        self.assertEqual(s, 201)

    def test_shorts_derivation_end_to_end(self):
        self._seed_parent("sh")
        s, result = self.req("/api/v1/kids/episodes/sh-ep/shorts", "POST", {"id": "sh-ep-shorts"})
        self.assertEqual(s, 201)
        self.assertIn("Shorts", result["episode"]["title"])
        self.assertEqual(result["derivation"]["parent_episode_id"], "sh-ep")
        self.assertEqual(result["preset"], "portrait_1080x1920")
        # child มี storyboard ย่อ + timeline พร้อม render ต่อแบบ portrait
        s, scenes = self.req("/api/v1/kids/episodes/sh-ep-shorts/scenes")
        self.assertEqual(s, 200)
        self.assertLessEqual(len(scenes["items"]), 3)
        s, render = self.req("/api/v1/kids/render-jobs", "POST",
                             {"episode_id": "sh-ep-shorts", "preset": "portrait_1080x1920"},
                             headers={"Idempotency-Key": "shorts-render-1"})
        self.assertEqual(s, 201)
        self.assertEqual(render["status"], "succeeded")
        # parent ไม่ถูกแตะต้อง
        s, parent_scenes = self.req("/api/v1/kids/episodes/sh-ep/scenes")
        self.assertEqual(len(parent_scenes["items"]), 4)
        # idempotent rerun
        s, again = self.req("/api/v1/kids/episodes/sh-ep/shorts", "POST", {"id": "sh-ep-shorts"},
                            headers={"Idempotency-Key": "shorts:sh-ep:sh-ep-shorts"})
        self.assertIn(s, (200, 201))

    def test_voice_profiles_and_clone_consent(self):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "vbrand", "name": "Voice Brand", "language": "en"})
        self.assertEqual(s, 201)
        s, voice = self.req("/api/v1/kids/voices", "POST", {"id": "lumi-voice", "name": "Lumi Narrator",
                                                             "provider": "mock", "model": "mock-tts-1",
                                                             "voice_id": "narrator-default", "language": "en"})
        self.assertEqual(s, 201)
        # clone โดยไม่มี consent ต้องถูกปฏิเสธ
        s, denied = self.req("/api/v1/kids/voices", "POST", {"id": "evil-clone", "name": "Clone",
                                                             "voice_id": "clone-someone", "language": "en"})
        self.assertEqual(s, 400)
        s, ok = self.req("/api/v1/kids/voices", "POST", {"id": "ok-clone", "name": "Consented Clone",
                                                         "voice_id": "clone-actor-a", "language": "en",
                                                         "rights": {"consent_ref": "consent-2026-001"}})
        self.assertEqual(s, 201)
        # preview ได้ไฟล์เสียง synthetic พร้อม provenance
        s, preview = self.req("/api/v1/kids/voices/preview", "POST", {"voice_id": "lumi-voice", "line": "Hello friends!"})
        self.assertEqual(s, 201)
        self.assertTrue(preview["artifact"]["sha256"])
        self.assertEqual(preview["asset"]["kind"], "audio")

    def test_music_requires_license(self):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "mbrand", "name": "Music Brand", "language": "en"})
        self.assertEqual(s, 201)
        s, denied = self.req("/api/v1/kids/music", "POST", {"title": "No License Song"})
        self.assertEqual(s, 400)
        s, track = self.req("/api/v1/kids/music", "POST", {"title": "Sunny Tune", "provider": "mock",
                                                            "license": "original-in-house-2026", "duration_seconds": 30})
        self.assertEqual(s, 201)
        self.assertEqual(track["license"], "original-in-house-2026")

    def test_brand_quota_blocks_extra_episodes(self):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "qbrand", "name": "Quota Brand", "language": "en",
                                                        "publishing": {"max_episodes": 1}})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes", "POST", {"id": "q-ep-1", "brand_id": "qbrand",
                                                          "title": "First", "summary": "ok"})
        self.assertEqual(s, 201)
        s, blocked = self.req("/api/v1/kids/episodes", "POST", {"id": "q-ep-2", "brand_id": "qbrand",
                                                                 "title": "Second", "summary": "ok"})
        self.assertEqual(s, 400)
        self.assertIn("quota", blocked["error"]["message"])

    def test_language_variant_is_draft_and_needs_review(self):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "lbrand", "name": "Lang Brand", "language": "en"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes", "POST", {"id": "l-ep", "brand_id": "lbrand",
                                                          "title": "Colors", "summary": "learn red and blue",
                                                          "age_band": "preschool", "language": "en",
                                                          "objectives": ["colors"], "vocabulary": ["red", "blue"]})
        self.assertEqual(s, 201)
        # ภาษาเดิมต้องถูกปฏิเสธ
        s, denied = self.req("/api/v1/kids/episodes/l-ep/variants", "POST", {"id": "l-ep-en", "language": "en"})
        self.assertEqual(s, 400)
        s, variant = self.req("/api/v1/kids/episodes/l-ep/variants", "POST", {"id": "l-ep-th", "language": "th"})
        self.assertEqual(s, 201)
        self.assertEqual(variant["episode"]["language"], "th")
        self.assertEqual(variant["translation_status"], "needs_review")
        self.assertIn("needs human review", variant["episode"]["summary"])
        self.assertEqual(variant["derivation"]["parent_episode_id"], "l-ep")
        # parent ยังเป็น en เหมือนเดิม
        s, parent = self.req("/api/v1/kids/episodes/l-ep")
        self.assertEqual(parent["language"], "en")

    def test_marketing_suggestions_are_labeled_estimates(self):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "mkbrand", "name": "Market Brand", "language": "en"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes", "POST", {"id": "mk-ep", "brand_id": "mkbrand",
                                                          "title": "Colors", "summary": "learn",
                                                          "objectives": ["colors"], "vocabulary": ["red"]})
        self.assertEqual(s, 201)
        s, suggestions = self.req("/api/v1/kids/episodes/mk-ep/marketing", "POST", {})
        self.assertEqual(s, 200)
        self.assertTrue(suggestions["estimated"])
        self.assertEqual(len(suggestions["titles"]), 3)
        self.assertIn("red", suggestions["keywords"])
        s, missing = self.req("/api/v1/kids/episodes/nope/marketing", "POST", {})
        self.assertEqual(s, 404)

    def test_analytics_summary_reflects_real_rows(self):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "abrand", "name": "Analytics Brand", "language": "en"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes", "POST", {"id": "a-ep", "brand_id": "abrand",
                                                          "title": "Ep", "summary": "ok"})
        self.assertEqual(s, 201)
        s, summary = self.req("/api/v1/kids/analytics/summary")
        self.assertEqual(s, 200)
        self.assertGreaterEqual(summary["episodes_by_status"].get("draft", 0), 1)
        self.assertIn("usage", summary)
        self.assertIn("note", summary)

    def test_async_queue_and_tick_flow(self):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "qbrand2", "name": "Queue Brand", "language": "en"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes", "POST", {"id": "q-ep", "brand_id": "qbrand2",
                                                          "title": "Queued", "summary": "ok"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes/q-ep/storyboard", "POST", {"num_scenes": 2})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes/q-ep/timeline", "POST", {})
        self.assertEqual(s, 201)
        # queue แบบ async ต้องค้างสถานะ queued (ยังไม่ render)
        s, queued = self.req("/api/v1/kids/render-jobs/queue", "POST", {"episode_id": "q-ep"},
                             headers={"Idempotency-Key": "queue-1"})
        self.assertEqual(s, 201)
        self.assertEqual(queued["status"], "queued")
        # tick ประมวลผลจนสำเร็จ
        s, ticked = self.req("/api/v1/kids/render-jobs/tick", "POST", {})
        self.assertEqual(s, 200)
        self.assertTrue(ticked["processed"])
        self.assertEqual(ticked["render_job"]["status"], "succeeded")
        self.assertTrue(ticked["render_job"]["output_sha256"])
        # tick ตอนคิวว่าง
        s, idle = self.req("/api/v1/kids/render-jobs/tick", "POST", {})
        self.assertEqual(s, 200)
        self.assertFalse(idle["processed"])

    def test_failed_job_dead_letters_after_three_attempts(self):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "dbrand", "name": "Dead Brand", "language": "en"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes", "POST", {"id": "d-ep", "brand_id": "dbrand",
                                                          "title": "Dead", "summary": "ok"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes/d-ep/storyboard", "POST", {"num_scenes": 1})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes/d-ep/timeline", "POST", {})
        self.assertEqual(s, 201)
        s, queued = self.req("/api/v1/kids/render-jobs/queue", "POST", {"episode_id": "d-ep"},
                             headers={"Idempotency-Key": "dead-1"})
        self.assertEqual(s, 201)
        # ลบ scenes ให้ render ล้มเหลวแบบ deterministic
        with self.db.connection() as c:
            c.execute("DELETE FROM kids_scenes WHERE tenant_id='default' AND episode_id='d-ep'")
        for _ in range(3):
            s, ticked = self.req("/api/v1/kids/render-jobs/tick", "POST", {})
            self.assertEqual(s, 200)
            self.assertTrue(ticked["processed"])
        self.assertTrue(ticked.get("dead_letter"))
        self.assertEqual(ticked["render_job"]["status"], "failed")
        self.assertEqual(ticked["render_job"]["attempts"], 3)

    def test_human_translation_fills_variant_scenes(self):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "tbrand", "name": "Trans Brand", "language": "en"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes", "POST", {"id": "t-ep", "brand_id": "tbrand",
                                                          "title": "Trans", "summary": "ok", "language": "th"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes/t-ep/storyboard", "POST", {"num_scenes": 2})
        self.assertEqual(s, 201)
        s, result = self.req("/api/v1/kids/episodes/t-ep/translation", "POST",
                             {"scenes": [{"id": "s01", "dialogue_line": "สวัสดีเพื่อนๆ"},
                                          {"id": "s02", "dialogue_line": "มาเรียนสีกัน"}]})
        self.assertEqual(s, 200)
        self.assertEqual(len(result["scenes"]), 2)
        lines = {sc["id"]: (sc.get("dialogue") or {}).get("line", "") for sc in result["scenes"]}
        self.assertEqual(lines["s01"], "สวัสดีเพื่อนๆ")
        # scene ที่ไม่มีอยู่ต้องถูกปฏิเสธ
        s, denied = self.req("/api/v1/kids/episodes/t-ep/translation", "POST",
                             {"scenes": [{"id": "s99", "dialogue_line": "x"}]})
        self.assertEqual(s, 400)

    def test_schedules_require_future_tz_and_reject_conflicts(self):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "sbrand", "name": "Sched Brand", "language": "en"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/channels", "POST", {"id": "sched-chan", "brand_id": "sbrand", "name": "Chan"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes", "POST", {"id": "s-ep", "brand_id": "sbrand",
                                                          "title": "Sched", "summary": "ok"})
        self.assertEqual(s, 201)
        # ไม่มี timezone ต้องถูกปฏิเสธ
        s, denied = self.req("/api/v1/kids/schedules", "POST", {"channel_id": "sched-chan", "episode_id": "s-ep",
                                                                 "slot_at": "2030-01-01T09:00:00"})
        self.assertEqual(s, 400)
        # slot อดีตต้องถูกปฏิเสธ
        s, denied = self.req("/api/v1/kids/schedules", "POST", {"channel_id": "sched-chan", "episode_id": "s-ep",
                                                                 "slot_at": "2020-01-01T09:00:00+00:00"})
        self.assertEqual(s, 400)
        slot = "2030-05-01T09:00:00+07:00"
        s, sched = self.req("/api/v1/kids/schedules", "POST", {"channel_id": "sched-chan", "episode_id": "s-ep",
                                                                "slot_at": slot, "timezone": "Asia/Bangkok"})
        self.assertEqual(s, 201)
        # จอง slot เดิมซ้ำต้อง conflict
        s, conflict = self.req("/api/v1/kids/schedules", "POST", {"channel_id": "sched-chan", "episode_id": "s-ep",
                                                                    "slot_at": slot})
        self.assertEqual(s, 409)
        s, listed = self.req("/api/v1/kids/schedules?channel_id=sched-chan")
        self.assertEqual(len(listed["items"]), 1)
        s, canceled = self.req(f"/api/v1/kids/schedules/{sched['id']}/cancel", "POST", {})
        self.assertEqual(s, 200)
        self.assertEqual(canceled["status"], "canceled")

    def test_provider_routes_resolve_with_disabled_externals(self):
        s, resolved = self.req("/api/v1/kids/providers/routes/llm")
        self.assertEqual(s, 200)
        self.assertEqual(resolved["primary"]["provider"], "mock")
        s, saved = self.req("/api/v1/kids/providers/routes", "POST", {"capability": "image",
                                                                       "providers": ["openai", "mock"]})
        self.assertEqual(s, 201)
        # openai ต้อง disabled จนกว่าจะมี operator config
        self.assertFalse(saved["resolved"]["route"][0]["enabled"])
        self.assertTrue(saved["resolved"]["route"][1]["enabled"])
        s, denied = self.req("/api/v1/kids/providers/routes", "POST", {"capability": "image",
                                                                         "providers": ["unknown-xyz"]})
        self.assertEqual(s, 400)
        s, denied = self.req("/api/v1/kids/providers/routes/nope")
        self.assertEqual(s, 404)

    def test_export_bundle_contains_full_episode(self):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "ebrand", "name": "Export Brand", "language": "en"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes", "POST", {"id": "e-ep", "brand_id": "ebrand",
                                                          "title": "Export", "summary": "ok"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes/e-ep/script", "POST", {"content_type": "nursery_rhyme",
                                                                       "body": {"verses": "hi"}})
        self.assertEqual(s, 201)
        s, bundle = self.req("/api/v1/kids/episodes/e-ep/export")
        self.assertEqual(s, 200)
        self.assertEqual(bundle["format"], "kids-export-1")
        self.assertEqual(bundle["episode"]["id"], "e-ep")
        self.assertEqual(len(bundle["scripts"]), 1)
        s, missing = self.req("/api/v1/kids/episodes/nope/export")
        self.assertEqual(s, 404)

    def test_export_import_round_trip_restores_creative_graph(self):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "rbrand", "name": "Restore Brand", "language": "en"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/characters", "POST", {"id": "rchar", "brand_id": "rbrand", "name": "Rimi"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes", "POST", {"id": "r-ep", "brand_id": "rbrand",
                                                          "title": "Restore Me", "summary": "learn shapes",
                                                          "objectives": ["shapes"], "vocabulary": ["circle"]})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes/r-ep/script", "POST", {"content_type": "nursery_rhyme",
                                                                       "body": {"verses": "round and round"}})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes/r-ep/storyboard", "POST", {"num_scenes": 2})
        self.assertEqual(s, 201)
        s, bundle = self.req("/api/v1/kids/episodes/r-ep/export")
        self.assertEqual(s, 200)
        # import เป็น id ใหม่
        s, restored = self.req("/api/v1/kids/episodes/import", "POST", {"bundle": bundle, "id": "r-ep-copy"})
        self.assertEqual(s, 201)
        self.assertEqual(restored["episode_id"], "r-ep-copy")
        self.assertEqual(restored["counts"]["scripts"], 1)
        self.assertEqual(restored["counts"]["scenes"], 2)
        s, scenes = self.req("/api/v1/kids/episodes/r-ep-copy/scenes")
        self.assertEqual(len(scenes["items"]), 2)
        # pipeline รันต่อบนสำเนาได้ (timeline ถูก restore มาด้วย)
        s, pipe = self.req("/api/v1/kids/episodes/r-ep-copy/pipeline", "POST", {"num_scenes": 2})
        self.assertEqual(s, 200)
        self.assertEqual(pipe["failed"], "")
        # approvals ไม่ติดมาด้วย — ต้องขอใหม่ (safety)
        s, approvals = self.req("/api/v1/kids/approvals?state=pending")
        restored_approvals = [a for a in approvals["items"] if a["episode_id"] == "r-ep-copy"]
        self.assertEqual(len(restored_approvals), 1)
        # import ซ้ำ id เดิมต้องถูกปฏิเสธ
        s, dupe = self.req("/api/v1/kids/episodes/import", "POST", {"bundle": bundle, "id": "r-ep-copy"})
        self.assertEqual(s, 400)
        # bundle ผิด format / ข้าม tenant ต้องถูกปฏิเสธ
        s, bad = self.req("/api/v1/kids/episodes/import", "POST", {"bundle": {"format": "nope"}})
        self.assertEqual(s, 400)
        evil = dict(bundle, tenant_id="other")
        s, cross = self.req("/api/v1/kids/episodes/import", "POST", {"bundle": evil, "id": "evil-copy"})
        self.assertEqual(s, 400)


class KidsHardeningTests(unittest.TestCase):
    """Regression tests for PR #285 review findings (safety, SoD, idempotency, honesty)."""

    def setUp(self):
        self.temp, self.settings, self.db, self.provider, self.engine, self.auth = stack()
        self.app = App(self.settings, self.db, self.engine, self.auth, self.provider)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.app.handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.engine.shutdown()
        self.temp.cleanup()

    def req(self, path, method="GET", body=None, headers=None, secret="test-admin-secret"):
        h = {"Authorization": f"Bearer {secret}", **(headers or {})}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        r = urllib.request.Request(self.base + path, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(r, timeout=60) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")

    def _brand_episode(self, prefix):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": f"{prefix}-b", "name": "H Brand", "language": "en"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes", "POST", {"id": f"{prefix}-e", "brand_id": f"{prefix}-b",
                                                          "title": "H Episode", "summary": "learn"})
        self.assertIn(s, (200, 201))

    def test_nested_secrets_rejected(self):
        s, denied = self.req("/api/v1/kids/brands", "POST", {"id": "evil-b", "name": "Evil",
                                                              "voice_defaults": {"api_key": "sk_1234567890123456"}})
        self.assertEqual(s, 400)
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "ok-b", "name": "Ok Brand"})
        self.assertEqual(s, 201)
        s, denied = self.req("/api/v1/kids/channels", "POST", {"id": "evil-c", "brand_id": "ok-b", "name": "C",
                                                                "publishing_settings": {"token": "ghp_1234567890123456"}})
        self.assertEqual(s, 400)

    def test_locked_character_rejects_edits(self):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "lb", "name": "Lock Brand"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/characters", "POST", {"id": "locky", "brand_id": "lb", "name": "Locky"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/characters/locky/lock", "POST", {})
        self.assertEqual(s, 200)
        s, denied = self.req("/api/v1/kids/characters", "POST", {"id": "locky", "brand_id": "lb", "name": "Changed"})
        self.assertEqual(s, 400)
        s, _ = self.req("/api/v1/kids/characters/locky/unlock", "POST", {})
        self.assertEqual(s, 200)
        s, _ = self.req("/api/v1/kids/characters", "POST", {"id": "locky", "brand_id": "lb", "name": "Changed"})
        self.assertEqual(s, 201)

    def test_storyboard_replace_drops_stale_scenes(self):
        self._brand_episode("sb")
        s, _ = self.req("/api/v1/kids/episodes/sb-e/storyboard", "POST", {"num_scenes": 4})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes/sb-e/storyboard", "POST", {"num_scenes": 2})
        self.assertEqual(s, 201)
        s, scenes = self.req("/api/v1/kids/episodes/sb-e/scenes")
        self.assertEqual(sorted(sc["id"] for sc in scenes["items"]), ["s01", "s02"])

    def test_timeline_ordering_unit(self):
        from zworkforce.kids_workflow import _order_scenes_for_timeline
        scenes = [{"id": "s01", "duration_seconds": 5}, {"id": "s02", "duration_seconds": 5}]
        timeline = {"version": 2, "tracks": {"video": [{"scene_id": "s02", "duration": 3.0}]}}
        ordered = _order_scenes_for_timeline(scenes, timeline, 2)
        self.assertEqual([s["id"] for s in ordered], ["s02"])
        self.assertEqual(ordered[0]["duration_seconds"], 3.0)
        # wrong timeline version falls back to full scene list
        self.assertEqual(len(_order_scenes_for_timeline(scenes, timeline, 1)), 2)
        self.assertEqual(len(_order_scenes_for_timeline(scenes, None, 0)), 2)

    def test_objectives_members_must_be_strings(self):
        s, denied = self.req("/api/v1/kids/brands", "POST", {"id": "ob", "name": "O Brand"})
        self.assertEqual(s, 201)
        s, denied = self.req("/api/v1/kids/episodes", "POST", {"id": "o-e", "brand_id": "ob",
                                                                 "title": "T", "objectives": [{"topic": "x"}]})
        self.assertEqual(s, 400)

    def test_idempotent_replay_beats_quota(self):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "qb", "name": "Q Brand",
                                                        "publishing": {"max_episodes": 1}})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes", "POST", {"id": "q-e1", "brand_id": "qb", "title": "One"},
                         headers={"Idempotency-Key": "quota-replay-1"})
        self.assertEqual(s, 201)
        s, replay = self.req("/api/v1/kids/episodes", "POST", {"id": "q-e1-dup", "brand_id": "qb", "title": "Dup"},
                             headers={"Idempotency-Key": "quota-replay-1"})
        self.assertEqual(s, 200)
        self.assertEqual(replay["id"], "q-e1")

    def test_stale_approval_cannot_publish(self):
        self._brand_episode("st")
        s, _ = self.req("/api/v1/kids/episodes/st-e/storyboard", "POST", {"num_scenes": 2})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes/st-e/timeline", "POST", {})
        self.assertEqual(s, 201)
        s, render = self.req("/api/v1/kids/render-jobs", "POST", {"episode_id": "st-e"})
        self.assertEqual(render["status"], "succeeded")
        s, approval = self.req("/api/v1/kids/approvals", "POST", {"episode_id": "st-e"})
        self.assertEqual(s, 201)
        _, reviewer_secret = self.auth.create_key("default", "st-reviewer", "admin", ["*"])
        s, _ = self.req(f"/api/v1/kids/approvals/{approval['id']}/approve", "POST", {}, secret=reviewer_secret)
        self.assertEqual(s, 200)
        # เปลี่ยน content หลัง approve
        s, _ = self.req("/api/v1/kids/episodes/st-e/scenes", "POST", {"id": "s99", "visual_prompt": "new scene"})
        self.assertEqual(s, 201)
        s, pub = self.req("/api/v1/kids/publishing/prepare", "POST", {"episode_id": "st-e",
                                                                       "render_job_id": render["id"],
                                                                       "approval_id": approval["id"]})
        self.assertEqual(s, 201)
        s, blocked = self.req(f"/api/v1/kids/publishing/{pub['id']}/publish", "POST", {})
        self.assertEqual(s, 400)

    def test_prepare_validates_render_job(self):
        self._brand_episode("rj")
        s, _ = self.req("/api/v1/kids/episodes/rj-e/storyboard", "POST", {"num_scenes": 1})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes/rj-e/timeline", "POST", {})
        self.assertEqual(s, 201)
        s, queued = self.req("/api/v1/kids/render-jobs/queue", "POST", {"episode_id": "rj-e"})
        self.assertEqual(s, 201)
        # queued (not succeeded) must be rejected at prepare time
        s, denied = self.req("/api/v1/kids/publishing/prepare", "POST", {"episode_id": "rj-e",
                                                                          "render_job_id": queued["id"]})
        self.assertEqual(s, 400)
        s, denied = self.req("/api/v1/kids/publishing/prepare", "POST", {"episode_id": "rj-e",
                                                                          "render_job_id": "deadbeefcafe"})
        self.assertEqual(s, 400)

    def test_direct_render_enforces_budget(self):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "bb", "name": "B Brand"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes", "POST", {"id": "b-e", "brand_id": "bb", "title": "B",
                                                          "budget_credits": 0.01})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes/b-e/storyboard", "POST", {"num_scenes": 2})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes/b-e/timeline", "POST", {})
        self.assertEqual(s, 201)
        s, denied = self.req("/api/v1/kids/render-jobs", "POST", {"episode_id": "b-e"})
        self.assertEqual(s, 400)

    def test_unreviewed_variant_blocked_until_translated(self):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "vb", "name": "V Brand"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes", "POST", {"id": "v-e", "brand_id": "vb", "title": "V", "language": "en"})
        self.assertEqual(s, 201)
        s, variant = self.req("/api/v1/kids/episodes/v-e/variants", "POST", {"id": "v-e-th", "language": "th"})
        self.assertEqual(s, 201)
        s, blocked = self.req("/api/v1/kids/publishing/prepare", "POST", {"episode_id": "v-e-th", "title": "T"})
        self.assertEqual(s, 400)

    def test_publish_usage_counted_once(self):
        self._brand_episode("uc")
        for step, payload in (("storyboard", {"num_scenes": 1}), ("timeline", {})):
            s, _ = self.req(f"/api/v1/kids/episodes/uc-e/{step}", "POST", payload)
            self.assertEqual(s, 201)
        s, render = self.req("/api/v1/kids/render-jobs", "POST", {"episode_id": "uc-e"})
        self.assertEqual(render["status"], "succeeded")
        s, approval = self.req("/api/v1/kids/approvals", "POST", {"episode_id": "uc-e"})
        _, reviewer_secret = self.auth.create_key("default", "uc-reviewer", "admin", ["*"])
        s, _ = self.req(f"/api/v1/kids/approvals/{approval['id']}/approve", "POST", {}, secret=reviewer_secret)
        self.assertEqual(s, 200)
        s, pub = self.req("/api/v1/kids/publishing/prepare", "POST", {"episode_id": "uc-e",
                                                                       "render_job_id": render["id"],
                                                                       "approval_id": approval["id"]})
        self.assertEqual(s, 201)
        before = self.db.kids_usage_summary("default")["cost_credits"]
        s, _ = self.req(f"/api/v1/kids/publishing/{pub['id']}/publish", "POST", {})
        self.assertEqual(s, 200)
        mid = self.db.kids_usage_summary("default")["cost_credits"]
        self.assertGreater(mid, before)
        s, _ = self.req(f"/api/v1/kids/publishing/{pub['id']}/publish", "POST", {})
        self.assertEqual(s, 200)
        after = self.db.kids_usage_summary("default")["cost_credits"]
        self.assertEqual(after, mid)

    def test_placeholder_render_fails_honestly(self):
        import shutil as _shutil
        self._brand_episode("ph")
        s, _ = self.req("/api/v1/kids/episodes/ph-e/storyboard", "POST", {"num_scenes": 1})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes/ph-e/timeline", "POST", {})
        self.assertEqual(s, 201)
        s, queued = self.req("/api/v1/kids/render-jobs/queue", "POST", {"episode_id": "ph-e"})
        self.assertEqual(s, 201)
        real_which = _shutil.which
        _shutil.which = lambda name: None
        try:
            s, ticked = self.req("/api/v1/kids/render-jobs/tick", "POST", {})
        finally:
            _shutil.which = real_which
        self.assertEqual(s, 200)
        self.assertNotEqual(ticked["render_job"]["status"], "succeeded")
        self.assertIn("FFmpeg", ticked["render_job"].get("error", "") + ticked.get("error", ""))

    def test_analytics_snapshot_is_audited(self):
        self._brand_episode("au")
        s, snap = self.req("/api/v1/kids/analytics/snapshot", "POST", {"episode_id": "au-e"})
        self.assertEqual(s, 201)
        s, audit = self.req("/api/v1/audit?limit=200")
        actions = [(e["action"], e["target_id"]) for e in audit["items"]]
        self.assertIn(("kids.analytics.snapshot", snap["id"]), actions)

    def test_asset_ids_are_server_scoped_per_tenant(self):
        self._brand_episode("ai")
        self.db.ensure_tenant("other", "Other")
        s, first = self.req("/api/v1/kids/assets", "POST", {"id": "logo", "name": "a.png",
                                                             "content_type": "image/png", "size_bytes": 5,
                                                             "episode_id": "ai-e", "sha256": "b" * 64})
        self.assertEqual(s, 201)
        other_headers = {"X-Tenant-ID": "other"}
        s, second = self.req("/api/v1/kids/assets", "POST", {"id": "logo", "name": "a.png",
                                                              "content_type": "image/png", "size_bytes": 5,
                                                              "sha256": "c" * 64}, headers=other_headers)
        self.assertEqual(s, 201)
        self.assertNotEqual(first["id"], second["id"])

    def test_mcp_parent_checks_and_parity(self):
        from zworkforce.mcp import _call_tool
        superadmin = type("P", (), {"name": "mcp-t", "role": "superadmin", "key_id": "k",
                                    "has_scope": lambda self, s: True})()
        with self.assertRaises(ValueError):
            _call_tool(self.app, superadmin, "default", "kids.create_episode_draft",
                       {"id": "x", "brand_id": "ghost", "title": "T"})
        with self.assertRaises(ValueError):
            _call_tool(self.app, superadmin, "default", "kids.create_storyboard",
                       {"episode_id": "ghost"})
        char_ep = "mcp-ep"
        self.db.kids_upsert_brand("default", "mcp-b", {"name": "M", "description": "", "age_range": "3-6",
                                                       "language": "en", "art_style": "", "music_style": "",
                                                       "voice_defaults": {}, "content_policy": {}, "publishing": {}},
                                  "t")
        from zworkforce.kids_factory import validate_episode
        self.db.kids_create_episode("default", char_ep, "mcp-b", validate_episode({"title": "T"}), "t")
        script = _call_tool(self.app, superadmin, "default", "kids.generate_script", {"episode_id": char_ep})
        self.assertEqual(self.db.kids_get_episode("default", char_ep)["status"], "scripted")
        self.assertGreater(self.db.kids_usage_summary("default")["cost_credits"], 0)


class KidsFullWorkflowsTests(unittest.TestCase):
    """Slice 9: worker fan-out, per-episode cost, bilingual end-to-end."""

    def setUp(self):
        self.temp, self.settings, self.db, self.provider, self.engine, self.auth = stack()
        self.app = App(self.settings, self.db, self.engine, self.auth, self.provider)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.app.handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.engine.shutdown()
        self.temp.cleanup()

    def req(self, path, method="GET", body=None, headers=None, secret="test-admin-secret"):
        h = {"Authorization": f"Bearer {secret}", **(headers or {})}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        r = urllib.request.Request(self.base + path, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(r, timeout=120) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")

    def _ready_episode(self, prefix, title="Work"):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": f"{prefix}-b", "name": "W Brand", "language": "en"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes", "POST", {"id": f"{prefix}-e", "brand_id": f"{prefix}-b",
                                                          "title": title, "summary": "learn"})
        self.assertIn(s, (200, 201))
        s, _ = self.req(f"/api/v1/kids/episodes/{prefix}-e/storyboard", "POST", {"num_scenes": 1})
        self.assertEqual(s, 201)
        s, _ = self.req(f"/api/v1/kids/episodes/{prefix}-e/timeline", "POST", {})
        self.assertEqual(s, 201)

    def test_tick_all_processes_bounded_batch(self):
        self._ready_episode("w1")
        self._ready_episode("w2")
        for ep, key in (("w1-e", "tick-all-1"), ("w2-e", "tick-all-2")):
            s, _ = self.req("/api/v1/kids/render-jobs/queue", "POST", {"episode_id": ep},
                             headers={"Idempotency-Key": key})
            self.assertEqual(s, 201)
        s, result = self.req("/api/v1/kids/render-jobs/tick-all", "POST", {"limit": 5})
        self.assertEqual(s, 200)
        self.assertEqual(result["processed"], 2)
        self.assertTrue(result["idle"])
        self.assertTrue(all(j["status"] == "succeeded" for j in result["jobs"]))
        s, empty = self.req("/api/v1/kids/render-jobs/tick-all", "POST", {"limit": 5})
        self.assertEqual(empty["processed"], 0)

    def test_episode_cost_breakdown(self):
        self._ready_episode("c1", title="Costly")
        s, render = self.req("/api/v1/kids/render-jobs", "POST", {"episode_id": "c1-e"})
        self.assertEqual(render["status"], "succeeded")
        s, cost = self.req("/api/v1/kids/episodes/c1-e/cost")
        self.assertEqual(s, 200)
        self.assertGreater(cost["total_cost_credits"], 0)
        self.assertTrue(cost["within_budget"])
        caps = {row["capability"] for row in cost["by_capability"]}
        self.assertIn("video_render", caps)
        s, missing = self.req("/api/v1/kids/episodes/nope/cost")
        self.assertEqual(s, 404)

    def test_thai_bilingual_end_to_end(self):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "th-b", "name": "Thai Brand", "language": "th"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes", "POST", {"id": "th-e", "brand_id": "th-b",
                                                          "title": "สีสัน", "summary": "เรียนสีห้าสี",
                                                          "age_band": "preschool", "language": "th",
                                                          "objectives": ["สี"], "vocabulary": ["แดง", "ฟ้า"]})
        self.assertEqual(s, 201)
        s, pipe = self.req("/api/v1/kids/episodes/th-e/pipeline", "POST", {"num_scenes": 2})
        self.assertEqual(s, 200)
        self.assertEqual(pipe["failed"], "")
        s, cost = self.req("/api/v1/kids/episodes/th-e/cost")
        self.assertGreaterEqual(cost["total_cost_credits"], 0)
        from zworkforce.mcp import _call_tool
        superadmin = type("P", (), {"name": "mcp-th", "role": "superadmin", "key_id": "k",
                                    "has_scope": lambda self, s: True})()
        summary = _call_tool(self.app, superadmin, "default", "kids.get_analytics_summary", {})
        self.assertGreaterEqual(summary["episodes_by_status"].get("in_review", 0), 1)
        ticked = _call_tool(self.app, superadmin, "default", "kids.tick_all_renders", {"limit": 5})
        self.assertIn("processed", ticked)
        epcost = _call_tool(self.app, superadmin, "default", "kids.get_episode_cost", {"episode_id": "th-e"})
        self.assertEqual(epcost["episode_id"], "th-e")


class KidsSlice10Tests(unittest.TestCase):
    """Slice 10: captions export, playlists, bench tool contract."""

    def setUp(self):
        self.temp, self.settings, self.db, self.provider, self.engine, self.auth = stack()
        self.app = App(self.settings, self.db, self.engine, self.auth, self.provider)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.app.handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.engine.shutdown()
        self.temp.cleanup()

    def req(self, path, method="GET", body=None, headers=None, secret="test-admin-secret"):
        h = {"Authorization": f"Bearer {secret}", **(headers or {})}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        r = urllib.request.Request(self.base + path, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(r, timeout=120) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")

    def test_captions_srt_vtt_json(self):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "cap-b", "name": "Cap Brand"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes", "POST", {"id": "cap-e", "brand_id": "cap-b", "title": "Cap"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes/cap-e/storyboard", "POST", {"num_scenes": 2})
        self.assertEqual(s, 201)
        s, srt = self.req("/api/v1/kids/episodes/cap-e/captions?format=srt")
        self.assertEqual(s, 200)
        self.assertEqual(srt["format"], "srt")
        self.assertIn("-->", srt["content"])
        self.assertIn("00:00:00,000 -->", srt["content"])
        s, vtt = self.req("/api/v1/kids/episodes/cap-e/captions?format=vtt")
        self.assertTrue(vtt["content"].startswith("WEBVTT"))
        self.assertIn(".000 -->", vtt["content"])
        s, js = self.req("/api/v1/kids/episodes/cap-e/captions?format=json")
        self.assertGreaterEqual(js["entries"], 1)
        s, denied = self.req("/api/v1/kids/episodes/cap-e/captions?format=ass")
        self.assertEqual(s, 400)
        s, missing = self.req("/api/v1/kids/episodes/nope/captions")
        self.assertEqual(s, 404)

    def test_playlists_resolve_episode_titles(self):
        s, _ = self.req("/api/v1/kids/brands", "POST", {"id": "pl-b", "name": "Pl Brand"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/episodes", "POST", {"id": "pl-e1", "brand_id": "pl-b", "title": "First"})
        self.assertEqual(s, 201)
        s, _ = self.req("/api/v1/kids/campaigns", "POST", {"id": "pl-c", "brand_id": "pl-b",
                                                            "name": "Camp", "playlist": ["pl-e1", "ghost-e"]})
        self.assertEqual(s, 201)
        s, lists = self.req("/api/v1/kids/playlists?brand_id=pl-b")
        self.assertEqual(s, 200)
        self.assertEqual(len(lists["items"]), 1)
        self.assertEqual(lists["items"][0]["episodes"][0]["title"], "First")
        self.assertEqual(lists["items"][0]["count"], 1)

    def test_mcp_captions_and_playlists(self):
        from zworkforce.mcp import _call_tool
        superadmin = type("P", (), {"name": "mcp-c", "role": "superadmin", "key_id": "k",
                                    "has_scope": lambda self, s: True})()
        with self.assertRaises(ValueError):
            _call_tool(self.app, superadmin, "default", "kids.export_captions", {"episode_id": "ghost"})
        with self.assertRaises(ValueError):
            _call_tool(self.app, superadmin, "default", "kids.resolve_provider", {"capability": "nope"})


if __name__ == "__main__":
    unittest.main()
