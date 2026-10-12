"""Kids episode pipeline: dependency-aware agent steps with checkpoints and budget gates.

Steps: research -> script -> storyboard -> assets -> timeline -> render -> qa -> approval_request.
Each step records a durable kids_agent_runs row keyed by idempotency key
(tenant, episode, step, source version) so reruns skip completed work
instead of duplicating side effects. Publishing itself is never auto-run:
it stays behind the human approval gate in db_kids.kids_publish_approved.
"""

from __future__ import annotations

from typing import Any

from .kids_factory import (
    KidsValidationError,
    build_storyboard,
    check_brand_quota,
    estimate_cost,
    kids_safety_check,
    render_deterministic_video,
    storyboard_to_timeline,
    validate_scene,
    validate_script,
)

PIPELINE_STEPS = ("research", "script", "storyboard", "assets", "timeline", "render", "qa", "approval_request")
AGENT_FOR_STEP = {
    "research": "research",
    "script": "script",
    "storyboard": "storyboard",
    "assets": "image",
    "timeline": "video_editor",
    "render": "video_editor",
    "qa": "quality",
    "approval_request": "publisher",
}
MAX_STEP_ATTEMPTS = 3


class KidsBudgetBlocked(ValueError):
    pass


def _idem(tenant_id: str, episode_id: str, step: str, version: str = "") -> str:
    return f"{tenant_id}:{episode_id}:{step}:{version}"


def check_budget(db, tenant_id: str, episode: dict, estimated: float) -> None:
    """Pre-execution cost approval: block when estimate exceeds episode budget."""
    budget = float(episode.get("budget_credits", 0) or 0)
    if budget > 0 and estimated > budget:
        raise KidsBudgetBlocked(
            f"estimated cost {estimated} credits exceeds episode budget {budget} credits; raise budget or reduce scope"
        )
    spent = db.kids_usage_summary(tenant_id).get("cost_credits", 0.0)
    if budget > 0 and spent + estimated > budget * 5:
        raise KidsBudgetBlocked("tenant spend ceiling would be exceeded by this run")


def run_episode_pipeline(app, tenant_id: str, episode_id: str, actor: str, *, preset: str = "landscape_1080p",
                         num_scenes: int = 4) -> dict[str, Any]:
    """Run the full pre-publish pipeline synchronously (bounded, deterministic)."""
    db = app.db
    episode = db.kids_get_episode(tenant_id, episode_id)
    if not episode:
        raise KidsValidationError("episode not found")
    completed: list[str] = []
    skipped: list[str] = []
    failed: str = ""

    def record(step: str, status: str, version: str = "", out: dict | None = None, err: str = "") -> bool:
        key = _idem(tenant_id, episode_id, step, version)
        _, created = db.kids_record_agent_run(tenant_id, episode_id, AGENT_FOR_STEP[step], step, status, actor,
                                              input_data={"episode_id": episode_id}, output_data=out or {},
                                              error=err, idempotency_key=key)
        (completed if status == "succeeded" else skipped if not created else completed).append(step)
        return created

    def already_done(step: str, version: str = "") -> bool:
        key = _idem(tenant_id, episode_id, step, version)
        with db.connection() as c:
            row = c.execute("SELECT status FROM kids_agent_runs WHERE tenant_id=? AND idempotency_key=?",
                            (tenant_id, key)).fetchone()
            return bool(row and (row[0] if not hasattr(row, "keys") else row["status"]) == "succeeded")

    # research: deterministic objectives check (mock provider, no spend)
    if not already_done("research", "v1"):
        record("research", "succeeded", "v1", {"objectives": episode.get("objectives", [])})
    else:
        skipped.append("research")

    # script: keep existing version or save a synthetic draft
    script = db.kids_latest_script(tenant_id, episode_id)
    if script is None:
        if not already_done("script", "v1"):
            body = {"hook": "Hello friends!", "concept": episode.get("summary", ""),
                    "verses": "Red bus, blue sky", "chorus": "Colors we love", "ending": "Great job!"}
            saved = db.kids_save_script(tenant_id, episode_id, validate_script({"content_type": "nursery_rhyme", "body": body}), actor)
            db.kids_set_episode_status(tenant_id, episode_id, "scripted", actor)
            record("script", "succeeded", "v1", {"version": saved.get("version", 1)})
        else:
            skipped.append("script")
    else:
        skipped.append("script")

    # storyboard
    scenes = db.kids_list_scenes(tenant_id, episode_id)
    if not scenes:
        if not already_done("storyboard", "v1"):
            script_body = ((db.kids_latest_script(tenant_id, episode_id) or {}).get("body")) or {}
            plan = build_storyboard(script_body=script_body, num_scenes=num_scenes)
            for index, item in enumerate(plan):
                db.kids_upsert_scene(tenant_id, episode_id, f"s{index + 1:02d}", validate_scene(item), actor)
            db.kids_set_episode_status(tenant_id, episode_id, "storyboarded", actor)
            record("storyboard", "succeeded", "v1", {"scenes": len(plan)})
        else:
            skipped.append("storyboard")
    else:
        skipped.append("storyboard")

    # assets: one synthetic asset per scene (mock, labeled)
    scenes = db.kids_list_scenes(tenant_id, episode_id)
    if not already_done("assets", "v1"):
        for scene in scenes:
            db.kids_register_asset(tenant_id, {"episode_id": episode_id, "scene_id": scene["id"], "kind": "image",
                                               "name": f"{scene['id']}-synthetic.png", "storage_uri": "synthetic://mock/pipeline",
                                               "sha256": "0" * 64, "size_bytes": 0,
                                               "provenance": {"provider": "mock", "synthetic": True}}, actor)
        record("assets", "succeeded", "v1", {"assets": len(scenes)})

    # timeline
    timeline = db.kids_latest_timeline(tenant_id, episode_id)
    if timeline is None:
        if not already_done("timeline", "v1"):
            tracks = storyboard_to_timeline(scenes)
            saved = db.kids_save_timeline(tenant_id, episode_id, tracks, actor)
            record("timeline", "succeeded", "v1", {"version": saved["version"], "checksum": saved["checksum"][:12]})
    else:
        skipped.append("timeline")

    # budget gate before render
    scenes = db.kids_list_scenes(tenant_id, episode_id)
    total = sum(float(s.get("duration_seconds", 5)) for s in scenes)
    estimated = estimate_cost(num_scenes=len(scenes), duration_total=total)
    try:
        check_budget(db, tenant_id, episode, estimated)
        check_brand_quota(db, tenant_id, episode.get("brand_id", ""), extra_cost=estimated)
    except KidsBudgetBlocked as exc:
        record("render", "blocked", "v1", {"estimated": estimated}, str(exc))
        return {"episode_id": episode_id, "completed": completed, "skipped": skipped, "failed": "render",
                "error": str(exc), "estimated_cost_credits": estimated}
    except KidsValidationError as exc:
        record("render", "blocked", "v1", {"estimated": estimated}, str(exc))
        return {"episode_id": episode_id, "completed": completed, "skipped": skipped, "failed": "render",
                "error": str(exc), "estimated_cost_credits": estimated}

    # render (bounded attempts, no blind retry of publish)
    timeline = db.kids_latest_timeline(tenant_id, episode_id)
    if timeline is None:
        record("render", "failed", "v1", {}, "no timeline")
        return {"episode_id": episode_id, "completed": completed, "skipped": skipped, "failed": "render", "error": "no timeline"}
    if not already_done("render", f"v{timeline.get('version', 1)}"):
        last_error = ""
        for attempt in range(1, MAX_STEP_ATTEMPTS + 1):
            try:
                job, created = db.kids_submit_render(tenant_id, episode_id, int(timeline.get("version", 1)), preset, actor,
                                                     idempotency_key=_idem(tenant_id, episode_id, "render_job", f"v{timeline.get('version', 1)}"))
                if not created and job.get("status") == "succeeded":
                    record("render", "succeeded", f"v{timeline.get('version', 1)}", {"render_job": job["id"]})
                    break
                render_dir = app.settings.data_dir / "kids-renders" / tenant_id
                render_dir.mkdir(parents=True, exist_ok=True)
                out_path = render_dir / f"{job['id']}.mp4"
                result = render_deterministic_video(scenes=scenes, preset=preset, title=episode.get("title", ""), out_path=out_path)
                try:
                    data = out_path.read_bytes()
                    artifact = app.artifacts.put_bytes(tenant_id, f"{episode_id}-{job['id']}.mp4", data, actor=actor,
                                                       content_type="video/mp4",
                                                       metadata={"kids_episode": episode_id, "kids_render": job["id"], "synthetic": True})
                    patch = {"status": "succeeded", "output_uri": artifact.get("storage_uri") or result["output_uri"],
                             "output_sha256": artifact.get("sha256", result["sha256"]),
                             "thumbnail_uri": result.get("thumbnail_uri", "")}
                except Exception:
                    patch = {"status": "succeeded", "output_uri": result["output_uri"],
                             "output_sha256": result["sha256"], "thumbnail_uri": result.get("thumbnail_uri", "")}
                db.kids_update_render(tenant_id, job["id"], patch, actor)
                db.kids_set_episode_status(tenant_id, episode_id, "rendered", actor)
                db.kids_record_usage(tenant_id, episode_id, "ffmpeg", "video_render", 1.0, 0.5)
                record("render", "succeeded", f"v{timeline.get('version', 1)}", {"render_job": job["id"]})
                break
            except Exception as exc:
                last_error = str(exc)[:500]
                if attempt == MAX_STEP_ATTEMPTS:
                    record("render", "failed", f"v{timeline.get('version', 1)}", {"attempts": attempt}, last_error)
                    return {"episode_id": episode_id, "completed": completed, "skipped": skipped,
                            "failed": "render", "error": last_error}
    else:
        skipped.append("render")

    # qa + approval request (safety gate, human decision still required)
    episode = db.kids_get_episode(tenant_id, episode_id)
    script = db.kids_latest_script(tenant_id, episode_id)
    scenes = db.kids_list_scenes(tenant_id, episode_id)
    corpus = (episode.get("summary", "") + " " + str((script or {}).get("body", "")) + " " +
              " ".join(s.get("visual_prompt", "") for s in scenes))
    report = kids_safety_check(age_band=episode.get("age_band", "preschool"), text=corpus)
    db.kids_save_moderation(tenant_id, episode_id, report, f"quality-agent:{actor}")
    if not report["passed"]:
        record("qa", "blocked", "v1", {}, f"safety blocked: {report['findings'][0]['rule']}")
        return {"episode_id": episode_id, "completed": completed, "skipped": skipped, "failed": "qa",
                "error": f"safety blocked: {report['findings'][0]['rule']}"}
    record("qa", "succeeded", "v1", {"passed": True})
    if not already_done("approval_request", "v1"):
        approval = db.kids_request_approval(tenant_id, episode_id, "episode", episode_id, int(episode.get("version", 1)), actor)
        db.kids_set_episode_status(tenant_id, episode_id, "in_review", actor)
        record("approval_request", "succeeded", "v1", {"approval_id": approval["id"]})
    else:
        skipped.append("approval_request")

    return {"episode_id": episode_id, "completed": sorted(set(completed)), "skipped": sorted(set(skipped)),
            "failed": failed, "estimated_cost_credits": estimated,
            "note": "publishing stays manual: approve then POST /api/v1/kids/publishing/prepare + .../publish"}
