#!/usr/bin/env python3
"""Local, zero-additional-cost video workflow prototype; not a production provider."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

STAGES = ("CREATED", "ANALYZED", "STORYBOARD_READY", "AWAITING_MANUAL_IMPORT", "MEDIA_READY", "RENDERED", "QA_PASSED", "AWAITING_APPROVAL", "APPROVED", "COMPLETED")
MAX_SOURCE_BYTES = 1_000_000_000
MAX_DURATION = 3600
SUPPORTED = {".mp4", ".mov", ".webm"}

class PipelineError(RuntimeError):
    pass

def execute(args: list[str], *, timeout: int = 180) -> str:
    try:
        p = subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        raise PipelineError(f"external process failed: {args[0]}") from exc
    return p.stdout

def probe(path: Path) -> dict:
    if not path.is_file() or path.is_symlink() or path.suffix.lower() not in SUPPORTED:
        raise PipelineError("unsupported or missing regular video")
    size = path.stat().st_size
    if size <= 0 or size > MAX_SOURCE_BYTES:
        raise PipelineError("source size exceeds limit")
    info = json.loads(execute(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], timeout=35))
    if not any(stream.get("codec_type") == "video" for stream in info.get("streams", [])):
        raise PipelineError("file does not contain a video stream")
    duration = float(info.get("format", {}).get("duration", 0))
    if not 0 < duration <= MAX_DURATION:
        raise PipelineError("invalid or excessive media duration")
    video = next(s for s in info["streams"] if s.get("codec_type") == "video")
    return {"duration_seconds": duration, "width": video.get("width"), "height": video.get("height"), "codec": video.get("codec_name"), "size_bytes": size}

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

class Store:
    def __init__(self, db: Path):
        db.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(str(db), timeout=15)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, tenant TEXT NOT NULL, stage TEXT NOT NULL, spec TEXT NOT NULL, updated INTEGER NOT NULL)")
        self.db.commit()

    def save(self, job: dict) -> None:
        with self.db:
            self.db.execute("INSERT INTO jobs (id,tenant,stage,spec,updated) VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET stage=excluded.stage,spec=excluded.spec,updated=excluded.updated", (job["id"], job["tenant"], job["stage"], json.dumps(job, sort_keys=True), int(time.time())))

    def load(self, tenant: str, job_id: str) -> dict:
        row = self.db.execute("SELECT spec FROM jobs WHERE tenant=? AND id=?", (tenant,job_id)).fetchone()
        if not row:
            raise PipelineError("job not found for tenant")
        return json.loads(row[0])

    def close(self):
        self.db.close()

def transition(job: dict, before: str, after: str):
    if job["stage"] != before:
        raise PipelineError(f"expected stage {before}, got {job['stage']}")
    job["stage"] = after

def safe_output(root: Path, job_id: str) -> Path:
    folder = root / job_id
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    return folder

def new_job(tenant: str, source: Path, root: Path, store: Store) -> dict:
    if not tenant or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in tenant):
        raise PipelineError("tenant must be an alphanumeric identifier")
    meta = probe(source)
    job = {"id": uuid.uuid4().hex, "tenant": tenant, "stage": "CREATED", "source": str(source.resolve()), "source_sha256": digest(source), "metadata": meta, "created": int(time.time()), "history": []}
    job["history"].append({"state": "CREATED", "at": int(time.time())})
    transition(job, "CREATED", "ANALYZED")
    job["scene_plan"] = [{"scene_id": f"scene_{i+1:02}", "start": round(i * meta["duration_seconds"] / min(8, max(1, int(meta["duration_seconds"] / 5))), 3), "description": "UNVERIFIED: requires human review"} for i in range(min(8, max(1, int(meta["duration_seconds"] / 5))))]
    transition(job, "ANALYZED", "STORYBOARD_READY")
    transition(job, "STORYBOARD_READY", "AWAITING_MANUAL_IMPORT")
    safe_output(root, job["id"]).joinpath("storyboard.json").write_text(json.dumps(job["scene_plan"], indent=2), encoding="utf-8")
    store.save(job)
    return job

def import_asset(job: dict, media: Path, root: Path, store: Store):
    if job["stage"] != "AWAITING_MANUAL_IMPORT":
        raise PipelineError("job not awaiting media import")
    meta = probe(media)
    job["media"] = str(media.resolve())
    job["media_sha256"] = digest(media)
    job["media_metadata"] = meta
    job["import_provenance"] = "human_supplied_unverified_rights"
    transition(job, "AWAITING_MANUAL_IMPORT", "MEDIA_READY")
    store.save(job)

def render(job: dict, root: Path, store: Store):
    if job["stage"] != "MEDIA_READY":
        raise PipelineError("job has no imported media")
    original = Path(job["media"])
    if not original.exists() or digest(original) != job["media_sha256"]:
        raise PipelineError("source changed since import")
    result = safe_output(root, job["id"]) / "rendered.mp4"
    scratch = result.with_name("rendering-" + uuid.uuid4().hex + ".mp4")
    try:
        execute(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(original), "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", str(scratch)], timeout=1200)
        meta = probe(scratch)
        os.replace(scratch, result)
    finally:
        scratch.unlink(missing_ok=True)
    job["rendered"] = str(result)
    job["rendered_sha256"] = digest(result)
    job["render_metadata"] = meta
    transition(job, "MEDIA_READY", "RENDERED")
    transition(job, "RENDERED", "QA_PASSED")
    transition(job, "QA_PASSED", "AWAITING_APPROVAL")
    store.save(job)

def approve(job: dict, store: Store, actor: str):
    if not actor.strip():
        raise PipelineError("explicit actor required")
    if job["stage"] != "AWAITING_APPROVAL":
        raise PipelineError("job has not passed QA")
    if not Path(job["rendered"]).exists() or digest(Path(job["rendered"])) != job["rendered_sha256"]:
        raise PipelineError("render hash verification failed")
    job["approval"] = {"actor": actor, "at": int(time.time()), "rights_attested_by_operator": True}
    transition(job, "AWAITING_APPROVAL", "APPROVED")
    transition(job, "APPROVED", "COMPLETED")
    store.save(job)

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Opt-in standalone Video Factory local runtime; no provider APIs")
    parser.add_argument("--db", type=Path, default=Path.home() / ".local/share/zeaz-video-factory/jobs.sqlite")
    parser.add_argument("--output", type=Path, default=Path.home() / ".local/share/zeaz-video-factory/artifacts")
    subs = parser.add_subparsers(dest="action", required=True)
    p = subs.add_parser("create"); p.add_argument("--tenant", required=True); p.add_argument("--source", type=Path, required=True)
    for name in ("status", "import", "render", "approve"):
        p = subs.add_parser(name); p.add_argument("--tenant", required=True); p.add_argument("--job", required=True)
        if name == "import": p.add_argument("--media", type=Path, required=True)
        if name == "approve": p.add_argument("--actor", required=True); p.add_argument("--confirm-rights", action="store_true")
    args = parser.parse_args(argv)
    store = Store(args.db)
    try:
        if args.action == "create": job = new_job(args.tenant, args.source, args.output, store)
        else:
            job = store.load(args.tenant, args.job)
            if args.action == "import": import_asset(job, args.media, args.output, store)
            if args.action == "render": render(job, args.output, store)
            if args.action == "approve":
                if not args.confirm_rights: raise PipelineError("explicit --confirm-rights required")
                approve(job, store, args.actor)
        print(json.dumps(job, indent=2, ensure_ascii=False))
        return 0
    except (PipelineError, ValueError, OSError) as exc:
        print(f"video factory: {exc}", file=sys.stderr)
        return 2
    finally:
        store.close()

if __name__ == "__main__":
    raise SystemExit(main())
