"""Kids Factory load baseline probe (operator tool, not a CI gate).

Boots an isolated temp stack, runs brand -> episode -> storyboard ->
timeline -> render -> export, and prints per-stage timings as JSON.
Numbers are environment-specific baselines, never production SLOs.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

from common import stack  # noqa: E402
from zworkforce.kids_factory import validate_brand, validate_episode, validate_scene  # noqa: E402
from zworkforce.kids_workflow import execute_render_job  # noqa: E402


def timed(label, fn, out):
    start = time.perf_counter()
    result = fn()
    out[label] = round(time.perf_counter() - start, 3)
    return result


def main() -> int:
    stages: dict[str, float] = {}
    temp, settings, db, provider, engine, auth = stack()
    try:
        timed("brand_upsert", lambda: db.kids_upsert_brand(
            "default", "bench", validate_brand({"name": "Bench", "language": "en"}), "bench"), stages)
        timed("episode_create", lambda: db.kids_create_episode(
            "default", "bench-ep", "bench", validate_episode({"title": "Bench Episode"}), "bench"), stages)

        def _board():
            from zworkforce.kids_factory import build_storyboard
            for i, item in enumerate(build_storyboard(script_body={"verses": "hi"}, num_scenes=2)):
                db.kids_upsert_scene("default", "bench-ep", f"s{i + 1:02d}", validate_scene(item), "bench")
        timed("storyboard_2_scenes", _board, stages)
        timed("timeline_save", lambda: db.kids_save_timeline(
            "default", "bench-ep", {"video": [], "captions": []}, "bench"), stages)
        timed("export_bundle", lambda: db.kids_export_episode("default", "bench-ep"), stages)
        job, _ = db.kids_submit_render("default", "bench-ep", 1, "landscape_1080p", "bench")
        timed("render_1080p_2_scenes", lambda: execute_render_job(
            _App(settings, db), "default", job["id"], "bench"), stages)
        print(json.dumps({"tool": "kids-bench", "stages_seconds": stages,
                          "note": "local baseline sample, not a production SLO"}, indent=2))
        return 0
    finally:
        engine.shutdown()
        temp.cleanup()


class _App:
    def __init__(self, settings, db):
        from zworkforce.artifacts import build_artifact_store
        self.settings = settings
        self.db = db
        self.artifacts = build_artifact_store(settings, db)


if __name__ == "__main__":
    raise SystemExit(main())
