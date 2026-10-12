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

    def req(self, path, method="GET", body=None, headers=None):
        h = {"Authorization": "Bearer test-admin-secret", **(headers or {})}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        r = urllib.request.Request(self.base + path, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
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
        # approve then 11 mock publish
        s, decided = self.req(f"/api/v1/kids/approvals/{approval['id']}/approve", "POST", {"comment": "reviewer ok"})
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


if __name__ == "__main__":
    unittest.main()
