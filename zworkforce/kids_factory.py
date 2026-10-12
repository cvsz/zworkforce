"""AI Kids Content Factory domain logic.

Deterministic, offline-capable vertical slice built on existing
zWorkforce primitives (artifacts, audit, budgets, approvals).
External generation defaults to mock/synthetic fixtures.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
AGE_BANDS = {"toddler", "preschool", "early-school", "2-4", "5-8"}
LANGUAGES = {"en", "th"}
CONTENT_TYPES = {
    "nursery_rhyme",
    "educational_song",
    "counting_song",
    "alphabet_song",
    "bedtime_story",
    "animal_story",
    "fairy_tale",
    "movement_song",
    "safety_lesson",
    "bilingual_learning",
    "animated_story",
}
RENDER_PRESETS = {
    "landscape_1080p": {"width": 1280, "height": 720, "fps": 24},
    "portrait_1080x1920": {"width": 720, "height": 1280, "fps": 24},
}
TIMELINE_TRACKS = ("video", "overlay", "voice", "music", "sfx", "captions", "branding")

# ห้ามทำซ้ำตัวละคร/เนื้อเพลงที่มีลิขสิทธิ์ — ใช้ blocklist แบบ deterministic
COPYRIGHTED_HINTS = (
    "cocomelon",
    "baby shark",
    "peppa pig",
    "disney",
    "frozen",
    "spider-man",
    "elsa",
    "mickey mouse",
)

DANGEROUS_HINTS = (
    "knife",
    "stranger follow",
    "jump from roof",
    "drink bleach",
    "run into traffic",
    "swallow coin",
    "play with fire",
    "มีด",
    "ปีนหลังคา",
    "วิ่งตัดหน้ารถ",
)

SECRET_LIKE = re.compile(
    r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*\S{8,}|"
    r"\b(sk|ghp|gho|zwf)_[A-Za-z0-9_\-]{12,}"
)


class KidsValidationError(ValueError):
    pass


def _slug(value: str, field: str) -> str:
    text = str(value or "").strip().lower()
    if not SLUG_RE.fullmatch(text):
        raise KidsValidationError(f"{field} must match [a-z0-9-], 2..63 chars")
    return text


def _text(value: Any, field: str, *, max_len: int = 500, required: bool = False) -> str:
    text = str(value if value is not None else "").strip()
    if required and not text:
        raise KidsValidationError(f"{field} is required")
    if len(text) > max_len:
        raise KidsValidationError(f"{field} exceeds {max_len} chars")
    if SECRET_LIKE.search(text):
        raise KidsValidationError(f"{field} looks like it contains a secret")
    return text


def _check_copyright(text: str) -> None:
    lowered = text.lower()
    for hint in COPYRIGHTED_HINTS:
        if hint in lowered:
            raise KidsValidationError(f"content references protected work '{hint}'; use original designs only")


def validate_brand(payload: dict[str, Any]) -> dict[str, Any]:
    name = _text(payload.get("name"), "brand.name", max_len=120, required=True)
    _check_copyright(name + " " + str(payload.get("description", "")))
    age_range = _text(payload.get("age_range", "3-6"), "brand.age_range", max_len=16) or "3-6"
    language = str(payload.get("language", "en")).strip().lower()
    if language not in LANGUAGES:
        raise KidsValidationError("brand.language must be 'en' or 'th'")
    return {
        "name": name,
        "description": _text(payload.get("description"), "brand.description", max_len=2000),
        "age_range": age_range,
        "language": language,
        "art_style": _text(payload.get("art_style"), "brand.art_style", max_len=200),
        "music_style": _text(payload.get("music_style"), "brand.music_style", max_len=200),
        "voice_defaults": dict(payload.get("voice_defaults") or {}),
        "content_policy": dict(payload.get("content_policy") or {}),
        "publishing": dict(payload.get("publishing") or {}),
    }


def validate_character(payload: dict[str, Any]) -> dict[str, Any]:
    name = _text(payload.get("name"), "character.name", max_len=80, required=True)
    _check_copyright(name + " " + str(payload.get("description", "")))
    return {
        "name": name,
        "role": _text(payload.get("role", "friend"), "character.role", max_len=40) or "friend",
        "description": _text(payload.get("description"), "character.description", max_len=1000),
        "species": _text(payload.get("species"), "character.species", max_len=80),
        "personality": list(payload.get("personality") or []),
        "voice_profile": dict(payload.get("voice_profile") or {}),
        "palette": list(payload.get("palette") or []),
        "costume": dict(payload.get("costume") or {}),
        "negative_prompt": _text(payload.get("negative_prompt"), "character.negative_prompt", max_len=1000),
    }


def validate_episode(payload: dict[str, Any]) -> dict[str, Any]:
    title = _text(payload.get("title"), "episode.title", max_len=160, required=True)
    _check_copyright(title + " " + str(payload.get("summary", "")))
    age_band = str(payload.get("age_band", "preschool")).strip().lower()
    if age_band not in AGE_BANDS:
        raise KidsValidationError(f"episode.age_band must be one of {sorted(AGE_BANDS)}")
    language = str(payload.get("language", "en")).strip().lower()
    if language not in LANGUAGES:
        raise KidsValidationError("episode.language must be 'en' or 'th'")
    return {
        "title": title,
        "summary": _text(payload.get("summary"), "episode.summary", max_len=2000),
        "age_band": age_band,
        "language": language,
        "objectives": list(payload.get("objectives") or []),
        "vocabulary": list(payload.get("vocabulary") or []),
        "budget_credits": max(0.0, float(payload.get("budget_credits", 0) or 0)),
    }


SCRIPT_SECTIONS = ("hook", "intro", "concept", "repetition", "dialogue", "verses", "chorus", "transitions", "ending")


def validate_script(payload: dict[str, Any]) -> dict[str, Any]:
    content_type = str(payload.get("content_type", "nursery_rhyme"))
    if content_type not in CONTENT_TYPES:
        raise KidsValidationError(f"script.content_type must be one of {sorted(CONTENT_TYPES)}")
    body = payload.get("body")
    if not isinstance(body, dict):
        raise KidsValidationError("script.body must be an object")
    for section in SCRIPT_SECTIONS:
        if section in body and len(str(body[section])) > 4000:
            raise KidsValidationError(f"script.body.{section} exceeds 4000 chars")
    joined = json.dumps(body, ensure_ascii=False).lower()
    _check_copyright(joined)
    return {"content_type": content_type, "body": body}


def validate_scene(payload: dict[str, Any]) -> dict[str, Any]:
    visual = _text(payload.get("visual_prompt"), "scene.visual_prompt", max_len=2000, required=True)
    _check_copyright(visual)
    duration = float(payload.get("duration_seconds", 5) or 5)
    if not 1 <= duration <= 60:
        raise KidsValidationError("scene.duration_seconds must be 1..60")
    ordering = int(payload.get("ordering", 0) or 0)
    if not 0 <= ordering <= 500:
        raise KidsValidationError("scene.ordering must be 0..500")
    return {
        "ordering": ordering,
        "duration_seconds": duration,
        "objective": _text(payload.get("objective"), "scene.objective", max_len=500),
        "visual_prompt": visual,
        "negative_prompt": _text(payload.get("negative_prompt"), "scene.negative_prompt", max_len=1000),
        "character_refs": list(payload.get("character_refs") or []),
        "camera": dict(payload.get("camera") or {}),
        "dialogue": dict(payload.get("dialogue") or {}),
        "music_cues": list(payload.get("music_cues") or []),
        "captions": list(payload.get("captions") or []),
        "asset_ids": list(payload.get("asset_ids") or []),
    }


def validate_timeline(payload: dict[str, Any]) -> dict[str, Any]:
    tracks = payload.get("tracks")
    if not isinstance(tracks, dict):
        raise KidsValidationError("timeline.tracks must be an object")
    for name in TIMELINE_TRACKS:
        if name in tracks and not isinstance(tracks[name], list):
            raise KidsValidationError(f"timeline.tracks.{name} must be a list")
    unknown = set(tracks) - set(TIMELINE_TRACKS)
    if unknown:
        raise KidsValidationError(f"timeline has unknown tracks: {sorted(unknown)}")
    return {"tracks": tracks}


def kids_safety_check(*, age_band: str, text: str) -> dict[str, Any]:
    """Deterministic safety review layer (rule-based, human approval still required)."""
    lowered = (text or "").lower()
    findings: list[dict[str, Any]] = []
    for hint in DANGEROUS_HINTS:
        if hint.lower() in lowered:
            findings.append({"rule": "dangerous_imitation", "match": hint, "severity": "block"})
    for hint in COPYRIGHTED_HINTS:
        if hint in lowered:
            findings.append({"rule": "third_party_ip", "match": hint, "severity": "block"})
    if "http://" in lowered or "https://" in lowered:
        findings.append({"rule": "external_link_review", "match": "url", "severity": "review"})
    extra: list[str] = []
    if age_band in ("2-4", "toddler"):
        extra = ["simple_vocabulary", "no_flashing", "calm_audio", "short_duration"]
    elif age_band in ("5-8", "early-school"):
        extra = ["clear_learning_goal", "no_flashing", "bounded_audio_peaks"]
    checklist = [
        {"item": "age_appropriate", "required": True},
        {"item": "no_dangerous_imitation", "required": True},
        {"item": "no_frightening Imagery".lower(), "required": True},
        {"item": "original_design_only", "required": True},
        {"item": "audio_peak_bounded", "required": True},
        *[{"item": name, "required": True} for name in extra],
    ]
    blocked = any(f["severity"] == "block" for f in findings)
    return {"passed": not blocked, "findings": findings, "checklist": checklist}


def build_storyboard(*, script_body: dict[str, Any], num_scenes: int = 4) -> list[dict[str, Any]]:
    """Build a deterministic timestamped scene plan from a structured script."""
    verses = script_body.get("verses") or script_body.get("concept") or "Learning together"
    chorus = script_body.get("chorus") or "Sing and learn"
    scenes: list[dict[str, Any]] = []
    cursor = 0.0
    for index in range(max(1, min(int(num_scenes or 4), 12))):
        duration = 6.0
        line = verses if index % 2 == 0 else chorus
        scenes.append(
            {
                "ordering": index,
                "duration_seconds": duration,
                "objective": f"Beat {index + 1}: reinforce learning objective",
                "visual_prompt": f"Original preschool scene {index + 1}: {str(line)[:120]}",
                "negative_prompt": "no scary faces, no violence, no brand logos, no copyrighted characters",
                "character_refs": [],
                "camera": {"shot": "wide", "movement": "slow_pan"},
                "dialogue": {"line": str(line)[:280]},
                "music_cues": [{"cue": "gentle_marimba", "at_seconds": cursor}],
                "captions": [{"text": str(line)[:80], "start": cursor, "end": cursor + duration}],
                "asset_ids": [],
                "starts_at": cursor,
            }
        )
        cursor += duration
    return scenes


def timeline_checksum(tracks: dict[str, Any]) -> str:
    canonical = json.dumps(tracks, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def estimate_cost(*, num_scenes: int, duration_total: float, provider: str = "mock") -> float:
    """Deterministic mock cost model (credits). Never bills real providers in tests."""
    return round(float(num_scenes) * 0.4 + float(duration_total) * 0.05, 4)


def storyboard_to_timeline(scenes: list[dict[str, Any]], *, brand_name: str = "") -> dict[str, list]:
    tracks: dict[str, list] = {name: [] for name in TIMELINE_TRACKS}
    cursor = 0.0
    for scene in sorted(scenes, key=lambda s: int(s.get("ordering", 0))):
        duration = float(scene.get("duration_seconds", 5))
        tracks["video"].append({"scene_id": scene.get("id", ""), "start": cursor, "duration": duration})
        for caption in scene.get("captions", []) or []:
            tracks["captions"].append({"scene_id": scene.get("id", ""), "text": str(caption.get("text", ""))[:120]})
        for cue in scene.get("music_cues", []) or []:
            tracks["music"].append({"cue": str(cue.get("cue", "gentle"))[:60], "at": cursor})
        dialogue = scene.get("dialogue") or {}
        if dialogue.get("line"):
            tracks["voice"].append({"scene_id": scene.get("id", ""), "line": str(dialogue["line"])[:280]})
        cursor += duration
    if brand_name:
        tracks["branding"].append({"overlay": f"{brand_name} watermark", "position": "bottom-right"})
    return tracks


def validate_media_upload(*, filename: str, content_type: str, size_bytes: int, max_bytes: int = 25 * 1024 * 1024) -> None:
    if not filename or len(filename) > 180:
        raise KidsValidationError("asset filename must be 1..180 chars")
    lowered = filename.lower()
    if ".." in filename or "/" in filename or "\\" in filename:
        raise KidsValidationError("asset filename must not contain path separators")
    if lowered.startswith(("http://", "https://", "file://")):
        raise KidsValidationError("asset filename must be a plain filename")
    allowed = {
        "image/png": (".png",),
        "image/jpeg": (".jpg", ".jpeg"),
        "audio/mpeg": (".mp3",),
        "audio/wav": (".wav",),
        "video/mp4": (".mp4",),
        "text/plain": (".txt", ".srt", ".vtt"),
    }
    if content_type not in allowed:
        raise KidsValidationError(f"unsupported content_type '{content_type}'")
    if not any(lowered.endswith(ext) for ext in allowed[content_type]):
        raise KidsValidationError("filename extension does not match content_type")
    if size_bytes <= 0 or size_bytes > max_bytes:
        raise KidsValidationError("asset size out of bounds")


def render_deterministic_video(
    *,
    scenes: list[dict[str, Any]],
    preset: str = "landscape_1080p",
    title: str = "LumiKids Sample",
    out_path: str | Path,
) -> dict[str, Any]:
    """Render a deterministic sample MP4 with FFmpeg (bounded subprocess, no shell).

    Falls back to a SHA-pinned placeholder file only when ffmpeg is missing,
    clearly labeled synthetic so mocks are never presented as real animation.
    """
    if preset not in RENDER_PRESETS:
        raise KidsValidationError(f"unknown render preset '{preset}'")
    spec = RENDER_PRESETS[preset]
    out = Path(out_path)
    if ".." in out.parts:
        raise KidsValidationError("render output path must not contain '..'")
    out.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = shutil.which("ffmpeg")
    total = sum(float(s.get("duration_seconds", 5)) for s in scenes) or 6.0
    total = min(max(total, 2.0), 30.0)
    if ffmpeg is None:
        payload = ("KIDS_SYNTHETIC_PLACEHOLDER|" + json.dumps(scenes, sort_keys=True) + "|" + preset).encode()
        out.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        return {"output_uri": f"file://{out.resolve()}", "sha256": digest, "size_bytes": len(payload),
                "synthetic": True, "duration_seconds": total}

    # สร้างคลิปสีพื้น deterministic ต่อ scene แล้ว concat (label ชัดเจนว่าเป็น sample)
    with tempfile.TemporaryDirectory(prefix="kids-render-") as tmp:
        tmpdir = Path(tmp)
        parts: list[Path] = []
        palette = ["skyblue", "lightgreen", "peachpuff", "lavender", "lightyellow", "mistyrose"]
        for index, scene in enumerate(scenes[:12]):
            color = palette[index % len(palette)]
            duration = min(max(float(scene.get("duration_seconds", 5)), 1.0), 10.0)
            part = tmpdir / f"part{index:02d}.mp4"
            cmd = [
                ffmpeg, "-y", "-v", "error",
                "-f", "lavfi", "-i",
                f"color=c={color}:s={spec['width']}x{spec['height']}:r={spec['fps']}:d={duration}",
                "-f", "lavfi", "-i", f"sine=frequency={440 + index * 40}:duration={duration}",
                "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "96k", str(part),
            ]
            completed = subprocess.run(cmd, capture_output=True, timeout=120, shell=False, check=False)
            if completed.returncode != 0 or not part.exists():
                raise RuntimeError(f"ffmpeg scene render failed: {completed.stderr.decode()[:500]}")
            parts.append(part)
        concat = tmpdir / "concat.txt"
        concat.write_text("".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
        cmd = [ffmpeg, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat),
               "-c", "copy", str(out)]
        completed = subprocess.run(cmd, capture_output=True, timeout=120, shell=False, check=False)
        if completed.returncode != 0 or not out.exists():
            raise RuntimeError(f"ffmpeg concat failed: {completed.stderr.decode()[:500]}")
        # ดึง thumbnail 1 เฟรม
        thumb = out.with_suffix(".thumb.png")
        subprocess.run([ffmpeg, "-y", "-v", "error", "-i", str(out), "-vframes", "1", str(thumb)],
                       capture_output=True, timeout=60, shell=False, check=False)
    data = out.read_bytes()
    return {"output_uri": f"file://{out.resolve()}", "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data), "synthetic": True, "duration_seconds": total,
            "thumbnail_uri": f"file://{thumb.resolve()}" if thumb.exists() else ""}


MOCK_YOUTUBE_SCOPES = ("youtube.upload", "youtube.readonly")


def prepare_youtube_metadata(*, title: str, description: str, audience: str = "madeForKids") -> dict[str, Any]:
    """Validate YouTube metadata. Never hardcode madeForKids=false."""
    clean_title = _text(title, "youtube.title", max_len=100, required=True)
    clean_desc = _text(description, "youtube.description", max_len=5000)
    if audience not in ("madeForKids", "notMadeForKids", "unspecified"):
        raise KidsValidationError("youtube.audience must be madeForKids/notMadeForKids/unspecified")
    return {"title": clean_title, "description": clean_desc, "audience": audience,
            "category": "Education", "synthetic_disclosure": True}


def mock_youtube_upload(*, metadata: dict[str, Any], idempotency_key: str, sha256: str) -> dict[str, Any]:
    """Deterministic mock upload: stable external_id from idempotency key, no network."""
    seed = hashlib.sha256(f"{idempotency_key}:{sha256}".encode()).hexdigest()
    return {"external_id": f"mock-yt-{seed[:11]}", "status": "uploaded_mock",
            "url": f"https://youtube.example/videos/{seed[:11]}", "metadata": metadata}


def validate_voice_profile(payload: dict[str, Any]) -> dict[str, Any]:
    """Voice profile with rights/consent metadata. Cloning requires documented consent."""
    name = _text(payload.get("name"), "voice.name", max_len=80, required=True)
    language = str(payload.get("language", "en")).strip().lower()
    if language not in LANGUAGES:
        raise KidsValidationError("voice.language must be 'en' or 'th'")
    speed = float(payload.get("speed", 1.0) or 1.0)
    if not 0.5 <= speed <= 2.0:
        raise KidsValidationError("voice.speed must be 0.5..2.0")
    voice_id = _text(payload.get("voice_id"), "voice.voice_id", max_len=120)
    rights = dict(payload.get("rights") or {})
    if voice_id.startswith("clone-") and not str(rights.get("consent_ref", "")).strip():
        raise KidsValidationError("voice cloning requires rights.consent_ref (documented authorization)")
    return {
        "name": name,
        "provider": _text(payload.get("provider", "mock"), "voice.provider", max_len=40) or "mock",
        "model": _text(payload.get("model", "mock-tts-1"), "voice.model", max_len=80) or "mock-tts-1",
        "voice_id": voice_id or "narrator-default",
        "language": language,
        "style": _text(payload.get("style", "cheerful"), "voice.style", max_len=40) or "cheerful",
        "speed": speed,
        "rights": rights,
    }


def validate_music_track(payload: dict[str, Any]) -> dict[str, Any]:
    """Music must carry provider + license provenance. AI output is not assumed copyright-free."""
    title = _text(payload.get("title"), "music.title", max_len=120, required=True)
    license_name = _text(payload.get("license"), "music.license", max_len=120, required=True)
    duration = float(payload.get("duration_seconds", 0) or 0)
    if not 0 <= duration <= 600:
        raise KidsValidationError("music.duration_seconds must be 0..600")
    return {
        "title": title,
        "provider": _text(payload.get("provider", "mock"), "music.provider", max_len=40) or "mock",
        "license": license_name,
        "provenance": dict(payload.get("provenance") or {}),
        "duration_seconds": duration,
    }


def synth_preview_wav(*, text: str, speed: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Deterministic synthetic voice preview (pure-python sine WAV, clearly labeled mock)."""
    import math
    import struct
    import wave
    from io import BytesIO
    seed = int(hashlib.sha256(text.encode()).hexdigest(), 16)
    duration = min(max(0.5, len(text) / (40.0 * max(0.5, speed))), 5.0)
    n = int(sample_rate * duration)
    buf = BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n):
            freq = 440 + (seed % 5) * 40
            sample = int(8000 * math.sin(2 * math.pi * freq * i / sample_rate))
            frames += struct.pack("<h", sample)
        wav.writeframes(bytes(frames))
    return buf.getvalue()


def check_brand_quota(db, tenant_id: str, brand_id: str, *, extra_episodes: int = 0, extra_cost: float = 0.0) -> None:
    """Enforce per-brand quotas declared in brand.publishing (max_episodes, max_cost_credits)."""
    brand = db.kids_get_brand(tenant_id, brand_id)
    if not brand:
        return
    quota = brand.get("publishing") or {}
    try:
        max_episodes = int(quota.get("max_episodes", 0) or 0)
    except (TypeError, ValueError):
        max_episodes = 0
    try:
        max_cost = float(quota.get("max_cost_credits", 0) or 0)
    except (TypeError, ValueError):
        max_cost = 0.0
    if max_episodes > 0:
        current = len(db.kids_list_episodes(tenant_id, brand_id=brand_id))
        if current + extra_episodes > max_episodes:
            raise KidsValidationError(f"brand quota exceeded: max_episodes={max_episodes} (have {current})")
    if max_cost > 0:
        spent = db.kids_usage_summary(tenant_id).get("cost_credits", 0.0)
        if spent + extra_cost > max_cost:
            raise KidsValidationError(f"brand quota exceeded: max_cost_credits={max_cost} (spent {spent})")
