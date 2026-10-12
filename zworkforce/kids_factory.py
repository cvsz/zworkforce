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
    "landscape_1080p": {"width": 1920, "height": 1080, "fps": 24},
    "portrait_1080x1920": {"width": 1080, "height": 1920, "fps": 24},
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


def _scan_nested(value: Any, field: str, *, _depth: int = 0) -> None:
    """Fail closed when nested settings smuggle secret-like values (never persisted to browser-visible reads)."""
    if _depth > 6:
        raise KidsValidationError(f"{field} is nested too deeply")
    if isinstance(value, str):
        if SECRET_LIKE.search(value):
            raise KidsValidationError(f"{field} looks like it contains a secret; use server-side secret references")
    elif isinstance(value, dict):
        for key, item in value.items():
            _scan_nested(item, f"{field}.{key}", _depth=_depth + 1)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _scan_nested(item, f"{field}[{index}]", _depth=_depth + 1)


def validate_brand(payload: dict[str, Any]) -> dict[str, Any]:
    name = _text(payload.get("name"), "brand.name", max_len=120, required=True)
    _check_copyright(name + " " + str(payload.get("description", "")))
    age_range = _text(payload.get("age_range", "3-6"), "brand.age_range", max_len=16) or "3-6"
    language = str(payload.get("language", "en")).strip().lower()
    if language not in LANGUAGES:
        raise KidsValidationError("brand.language must be 'en' or 'th'")
    voice_defaults = dict(payload.get("voice_defaults") or {})
    content_policy = dict(payload.get("content_policy") or {})
    publishing = dict(payload.get("publishing") or {})
    _scan_nested(voice_defaults, "brand.voice_defaults")
    _scan_nested(content_policy, "brand.content_policy")
    _scan_nested(publishing, "brand.publishing")
    return {
        "name": name,
        "description": _text(payload.get("description"), "brand.description", max_len=2000),
        "age_range": age_range,
        "language": language,
        "art_style": _text(payload.get("art_style"), "brand.art_style", max_len=200),
        "music_style": _text(payload.get("music_style"), "brand.music_style", max_len=200),
        "voice_defaults": voice_defaults,
        "content_policy": content_policy,
        "publishing": publishing,
    }


CHANNEL_PLATFORMS = ("youtube", "youtube_mock", "tiktok", "facebook", "instagram")


def validate_channel(payload: dict[str, Any]) -> dict[str, Any]:
    name = _text(payload.get("name"), "channel.name", max_len=160, required=True)
    platform = str(payload.get("platform", "youtube")).strip().lower()
    if platform not in CHANNEL_PLATFORMS:
        raise KidsValidationError(f"channel.platform must be one of {list(CHANNEL_PLATFORMS)}")
    external_ref = _text(payload.get("external_account_ref"), "channel.external_account_ref", max_len=200)
    _scan_nested(external_ref, "channel.external_account_ref")
    settings = dict(payload.get("publishing_settings") or {})
    _scan_nested(settings, "channel.publishing_settings")
    return {"name": name, "platform": platform, "external_account_ref": external_ref, "publishing_settings": settings}


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


def _bounded_str_list(values: Any, field: str, *, max_items: int = 40, max_len: int = 120) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise KidsValidationError(f"{field} must be a list of strings")
    if len(values) > max_items:
        raise KidsValidationError(f"{field} exceeds {max_items} entries")
    cleaned: list[str] = []
    for item in values:
        if not isinstance(item, str):
            raise KidsValidationError(f"{field} entries must be strings")
        text = item.strip()
        if not text:
            continue
        if len(text) > max_len:
            raise KidsValidationError(f"{field} entry exceeds {max_len} chars")
        if SECRET_LIKE.search(text):
            raise KidsValidationError(f"{field} entry looks like it contains a secret")
        cleaned.append(text)
    return cleaned


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
        "objectives": _bounded_str_list(payload.get("objectives"), "episode.objectives"),
        "vocabulary": _bounded_str_list(payload.get("vocabulary"), "episode.vocabulary"),
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
    dialogue = payload.get("dialogue") or {}
    if not isinstance(dialogue, dict):
        raise KidsValidationError("scene.dialogue must be an object")
    _scan_nested(dialogue, "scene.dialogue")
    captions = payload.get("captions") or []
    if not isinstance(captions, list):
        raise KidsValidationError("scene.captions must be a list")
    _scan_nested(captions, "scene.captions")
    music_cues = payload.get("music_cues") or []
    if not isinstance(music_cues, list):
        raise KidsValidationError("scene.music_cues must be a list")
    character_refs = payload.get("character_refs") or []
    if not isinstance(character_refs, list):
        raise KidsValidationError("scene.character_refs must be a list")
    asset_ids = payload.get("asset_ids") or []
    if not isinstance(asset_ids, list):
        raise KidsValidationError("scene.asset_ids must be a list")
    camera = payload.get("camera") or {}
    if not isinstance(camera, dict):
        raise KidsValidationError("scene.camera must be an object")
    return {
        "ordering": ordering,
        "duration_seconds": duration,
        "objective": _text(payload.get("objective"), "scene.objective", max_len=500),
        "visual_prompt": visual,
        "negative_prompt": _text(payload.get("negative_prompt"), "scene.negative_prompt", max_len=1000),
        "character_refs": [str(x)[:64] for x in character_refs],
        "camera": camera,
        "dialogue": dialogue,
        "music_cues": music_cues,
        "captions": captions,
        "asset_ids": [str(x)[:32] for x in asset_ids],
    }


def build_safety_corpus(*, episode: dict[str, Any], script: dict[str, Any] | None,
                        scenes: list[dict[str, Any]], timeline: dict[str, Any] | None) -> str:
    """Single shared corpus for every transport: script, visuals, dialogue, captions, timeline tracks."""
    parts: list[str] = [str(episode.get("summary", ""))]
    body = ((script or {}).get("body")) or {}
    if isinstance(body, dict):
        parts.append(" ".join(str(v) for v in body.values()))
    for scene in scenes or []:
        parts.append(str(scene.get("visual_prompt", "")))
        dialogue = scene.get("dialogue") or {}
        if isinstance(dialogue, dict) and dialogue.get("line"):
            parts.append(str(dialogue["line"]))
        for caption in scene.get("captions") or []:
            if isinstance(caption, dict):
                parts.append(str(caption.get("text", "")))
            else:
                parts.append(str(caption))
    tracks = ((timeline or {}).get("tracks")) or {}
    if isinstance(tracks, dict):
        for name in ("voice", "captions"):
            for entry in tracks.get(name) or []:
                if isinstance(entry, dict):
                    parts.append(str(entry.get("line", entry.get("text", ""))))
    return " ".join(p for p in parts if p)


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
                "synthetic": True, "placeholder": True, "duration_seconds": total}

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
            "size_bytes": len(data), "synthetic": True, "placeholder": False, "duration_seconds": total,
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
        current = db.kids_count_episodes(tenant_id, brand_id)
        if current + extra_episodes > max_episodes:
            raise KidsValidationError(f"brand quota exceeded: max_episodes={max_episodes} (have {current})")
    if max_cost > 0:
        spent = db.kids_usage_summary(tenant_id).get("cost_credits", 0.0)
        if spent + extra_cost > max_cost:
            raise KidsValidationError(f"brand quota exceeded: max_cost_credits={max_cost} (spent {spent})")


def build_language_variant(*, parent: dict[str, Any], language: str) -> dict[str, Any]:
    """Draft a language variant shell. Machine text is NEVER presented as final.

    Returns child episode fields with translation_status needs_review; human
    translators must fill dialogue/captions before render/publish.
    """
    language = str(language or "").strip().lower()
    if language not in LANGUAGES:
        raise KidsValidationError("variant language must be 'en' or 'th'")
    if language == str(parent.get("language", "en")).strip().lower():
        raise KidsValidationError("variant language must differ from the parent episode language")
    return {
        "title": f"{parent.get('title', '')} [{language} draft]",
        "summary": f"{parent.get('summary', '')} [Machine draft in {language} — needs human review]",
        "age_band": parent.get("age_band", "preschool"),
        "language": language,
        "objectives": list(parent.get("objectives", []) or []),
        "vocabulary": list(parent.get("vocabulary", []) or []),
        "budget_credits": 0.0,
        "translation_status": "needs_review",
    }


def suggest_marketing(*, episode: dict[str, Any], brand_name: str = "") -> dict[str, Any]:
    """Deterministic mock marketing suggestions. All forecasts labeled estimates.

    Never automates spam, fake engagement, or deceptive targeting; output is a
    human-editable draft only.
    """
    title = str(episode.get("title", "Kids video"))
    objectives = list(episode.get("objectives", []) or ["learning"])
    vocabulary = list(episode.get("vocabulary", []) or [])
    keywords = sorted({w.lower() for w in (objectives + vocabulary) if w})[:10]
    return {
        "titles": [f"{title} — Learn Together!", f"{title} | Fun Lesson for Preschool", f"Sing and Learn: {title}"],
        "description_draft": f"{title}. {str(episode.get('summary', ''))[:200]} Made for preschool learning.",
        "keywords": keywords,
        "thumbnail_concepts": [
            f"Bright bus with big color blocks and the word '{(vocabulary[0] if vocabulary else 'Colors')}'",
            f"{brand_name + ' friends' if brand_name else 'Friends'} waving beside a rainbow",
        ],
        "playlist_suggestion": f"{brand_name} Learning" if brand_name else "Learning",
        "estimated": True,
        "note": "Estimates only; performance forecasts are not guarantees. No engagement automation.",
    }


PROVIDER_CAPABILITIES = ("llm", "image", "video", "tts", "music", "embeddings", "storage", "publishing")
KNOWN_PROVIDERS = ("mock", "ffmpeg", "youtube_mock", "openai", "gemini", "elevenlabs", "replicate", "runway", "local")
# Real providers stay disabled until operator config + external evidence exist.
CONFIGURED_PROVIDERS = ("mock", "ffmpeg", "youtube_mock", "local")
PROVIDER_BASE_COST = {"llm": 0.2, "image": 0.4, "video": 1.0, "tts": 0.1, "music": 0.3,
                      "embeddings": 0.05, "storage": 0.01, "publishing": 0.1}


def validate_schedule_slot(*, slot_at: str, timezone_name: str = "UTC") -> dict[str, str]:
    """Timezone-aware future slot validation (ISO-8601, tz required, no past slots)."""
    from datetime import datetime, timezone as _tz
    raw = str(slot_at or "").strip()
    if not raw:
        raise KidsValidationError("schedule.slot_at is required (ISO-8601 with timezone)")
    normalized = raw.replace("Z", "+00:00") if raw.endswith(("Z", "z")) else raw
    try:
        moment = datetime.fromisoformat(normalized)
    except ValueError:
        raise KidsValidationError("schedule.slot_at must be ISO-8601 (e.g. 2026-10-20T09:00:00+07:00)")
    if moment.tzinfo is None:
        raise KidsValidationError("schedule.slot_at must include a timezone offset")
    now = datetime.now(_tz.utc)
    if moment.astimezone(_tz.utc) <= now:
        raise KidsValidationError("schedule.slot_at must be in the future")
    tz_name = str(timezone_name or "UTC").strip()[:64] or "UTC"
    return {"slot_at": moment.isoformat(), "timezone": tz_name}


def validate_provider_route(*, capability: str, providers: list) -> dict[str, Any]:
    """Ordered provider route per capability. Unknown or duplicate entries fail closed."""
    if capability not in PROVIDER_CAPABILITIES:
        raise KidsValidationError(f"provider capability must be one of {list(PROVIDER_CAPABILITIES)}")
    if not isinstance(providers, list) or not 1 <= len(providers) <= 4:
        raise KidsValidationError("route providers must be a list of 1..4 provider names")
    seen: list[str] = []
    for name in providers:
        pname = str(name or "").strip().lower()
        if pname not in KNOWN_PROVIDERS:
            raise KidsValidationError(f"unknown provider '{name}'")
        if pname in seen:
            raise KidsValidationError(f"duplicate provider '{pname}' in route")
        seen.append(pname)
    return {"capability": capability, "providers": seen}


def resolve_provider_route(*, capability: str, providers: list[str]) -> dict[str, Any]:
    """Resolve an ordered route with enabled flags and cost preview.

    Real providers resolve as disabled until operator configuration and
    external evidence exist; the router never silently swaps fidelity tiers.
    """
    base = PROVIDER_BASE_COST.get(capability, 0.1)
    route = []
    for index, name in enumerate(providers):
        enabled = name in CONFIGURED_PROVIDERS
        route.append({"provider": name, "position": index, "enabled": enabled,
                      "mode": "mock" if name in ("mock", "youtube_mock") else ("local" if name in ("ffmpeg", "local") else "external"),
                      "estimated_cost_credits": round(base * (1.0 + index * 0.5), 4),
                      "note": "" if enabled else "requires operator configuration + external evidence"})
    return {"capability": capability, "route": route, "primary": route[0] if route else None}
