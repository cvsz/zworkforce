"""Core domain models, validation, and multi-agent workflow logic for ZEAZVERSE."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .zeazverse_bibles import (
    CANONICAL_CHARACTERS,
    CHANNEL_SETUP_STEPS,
    CONTENT_CLASSES,
    GLOBAL_NEGATIVE_PROMPT,
    PUBLISHING_STATES,
    ZEAZVERSE_BRAND,
)

SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,62}$")


class ZeazverseValidationError(ValueError):
    """Raised when ZEAZVERSE domain validation fails."""


def validate_slug(value: str, field_name: str = "id") -> str:
    s = str(value or "").strip().lower()
    if not SLUG_PATTERN.fullmatch(s):
        raise ZeazverseValidationError(f"{field_name} must match ^[a-z0-9][a-z0-9_-]{{1,62}}$, got: '{value}'")
    return s


def validate_character_data(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ZeazverseValidationError("Character must be a JSON object")
    char_id = validate_slug(data.get("id", ""), "character.id")
    name = str(data.get("name", "")).strip()
    if not name:
        raise ZeazverseValidationError("character.name cannot be empty")
    age = int(data.get("age", 21))
    if age < 21:
        raise ZeazverseValidationError(f"ZEAZVERSE idols must be adult 21+, got: {age}")
    nationality = str(data.get("nationality", "Thai")).strip()
    if not nationality:
        raise ZeazverseValidationError("character.nationality cannot be empty")
    costume_config = data.get("costume_config", data.get("costume", {}))
    if not isinstance(costume_config, dict):
        raise ZeazverseValidationError("character.costume must be an object")
    accessories = data.get("accessories", costume_config.get("accessories", []))
    if not isinstance(accessories, list):
        raise ZeazverseValidationError("character.accessories must be a list")
    return {
        "id": char_id,
        "name": name,
        "archetype": str(data.get("archetype", "Original")),
        "age": age,
        "nationality": nationality,
        "appearance": data.get("appearance", {}),
        "personality": data.get("personality", {}),
        "story_themes": data.get("story_themes", []),
        "dialogue_style": data.get("dialogue_style", {}),
        "voice_profile": data.get("voice_profile", {}),
        "costume_config": costume_config,
        "accessories": accessories,
        "consistency_rules": data.get("consistency_rules", {}),
        "reference_turnaround": data.get("reference_turnaround", {}),
        "status": data.get("status", "canonical"),
        "version": int(data.get("version", 1)),
    }


def validate_series_data(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ZeazverseValidationError("Series must be a JSON object")
    series_id = validate_slug(data.get("id", ""), "series.id")
    title = str(data.get("title", "")).strip()
    if not title:
        raise ZeazverseValidationError("series.title cannot be empty")
    content_class = str(data.get("content_class", "Cyberpunk Stories"))
    if content_class not in CONTENT_CLASSES:
        raise ZeazverseValidationError(f"Invalid content class: {content_class}. Must be one of {CONTENT_CLASSES}")
    return {
        "id": series_id,
        "title": title,
        "synopsis": str(data.get("synopsis", "")).strip(),
        "content_class": content_class,
        "target_format": str(data.get("target_format", "9:16")),
        "status": str(data.get("status", "active")),
        "metadata": data.get("metadata", {}),
    }


def validate_episode_data(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ZeazverseValidationError("Episode must be a JSON object")
    ep_id = validate_slug(data.get("id", ""), "episode.id")
    series_id = validate_slug(data.get("series_id", ""), "episode.series_id")
    title = str(data.get("title", "")).strip()
    if not title:
        raise ZeazverseValidationError("episode.title cannot be empty")
    content_class = str(data.get("content_class", "Cyberpunk Stories"))
    if content_class not in CONTENT_CLASSES:
        raise ZeazverseValidationError(f"Invalid content_class '{content_class}'")
    status = str(data.get("status", "IDEA"))
    if status not in PUBLISHING_STATES:
        raise ZeazverseValidationError(f"Invalid episode status: {status}")
    target_duration = float(data.get("target_duration_seconds", 30.0))
    if target_duration <= 0 or target_duration > 300.0:
        raise ZeazverseValidationError("Target duration must be between 1 and 300 seconds")
    return {
        "id": ep_id,
        "series_id": series_id,
        "channel_id": str(data.get("channel_id", "")).strip(),
        "story_id": str(data.get("story_id", "")).strip() or f"story-{ep_id}",
        "title": title,
        "content_class": content_class,
        "canvas_format": str(data.get("canvas_format", "1080x1920")),
        "fps": int(data.get("fps", 30)),
        "target_duration_seconds": target_duration,
        "status": status,
        "story_concept": data.get("story_concept", {}),
        "characters": data.get("characters", []),
        "script": data.get("script", {}),
        "storyboard": data.get("storyboard", {}),
        "asset_manifest": data.get("asset_manifest", {}),
        "render_manifest": data.get("render_manifest", {}),
        "audio_plan": data.get("audio_plan", {}),
        "editing_plan": data.get("editing_plan", {}),
        "qa_report": data.get("qa_report", {}),
        "publishing_metadata": data.get("publishing_metadata", {}),
        "version": int(data.get("version", 1)),
        "idempotency_key": str(data.get("idempotency_key", "")).strip(),
    }


def validate_scene_data(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ZeazverseValidationError("Scene must be a JSON object")
    scene_id = validate_slug(data.get("id", ""), "scene.id")
    time_start = float(data.get("time_start_seconds", 0.0))
    time_end = float(data.get("time_end_seconds", 5.0))
    if time_end <= time_start:
        raise ZeazverseValidationError(f"Scene time_end ({time_end}) must be greater than time_start ({time_start})")
    positive_prompt = str(data.get("positive_prompt", "")).strip()
    if not positive_prompt:
        raise ZeazverseValidationError("Scene positive_prompt cannot be empty")
    negative_prompt = str(data.get("negative_prompt", "")).strip() or GLOBAL_NEGATIVE_PROMPT

    return {
        "id": scene_id,
        "ordering": int(data.get("ordering", 0)),
        "time_start_seconds": time_start,
        "time_end_seconds": time_end,
        "characters": data.get("characters", []),
        "character_ref_ids": data.get("character_ref_ids", []),
        "environment": str(data.get("environment", "")),
        "subject_action": str(data.get("subject_action", "")),
        "camera_framing": str(data.get("camera_framing", "Medium Shot")),
        "camera_movement": str(data.get("camera_movement", "Slow push-in")),
        "lighting": str(data.get("lighting", "Neon cyberpunk sidelight")),
        "physical_interaction": str(data.get("physical_interaction", "")),
        "dialogue": data.get("dialogue", {}),
        "audio": data.get("audio", {}),
        "positive_prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "first_frame_continuity": str(data.get("first_frame_continuity", "")),
        "last_frame_continuity": str(data.get("last_frame_continuity", "")),
        "generation_model": str(data.get("generation_model", "mock-video-v1")),
        "model_settings": data.get("model_settings", {}),
        "expected_output": str(data.get("expected_output", "30fps 1080x1920 MP4")),
        "qa_checks": data.get("qa_checks", []),
        "status": str(data.get("status", "pending")),
        "output_artifact_uri": str(data.get("output_artifact_uri", "")),
    }


def generate_cinematic_storyboard(
    episode: dict[str, Any], characters: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Build a structured 5-act 30s storyboard following the cinematic standard."""
    characters = characters or [CANONICAL_CHARACTERS["lalin"]]
    char_names = [c.get("name", "LALIN") for c in characters]
    primary_char = characters[0] if characters else CANONICAL_CHARACTERS["lalin"]
    char_id = primary_char.get("id", "lalin")
    primary_name = primary_char.get("name", "LALIN")

    acts = [
        {
            "id": "scene_01_hook",
            "ordering": 0,
            "time_start_seconds": 0.0,
            "time_end_seconds": 3.0,
            "subject_action": f"{primary_name} gazes into a neon-lit futuristic Bangkok skyline at twilight",
            "camera_framing": "Extreme Close-Up to Wide pull-out",
            "camera_movement": "Dynamic cinematic zoom out",
            "lighting": "Vibrant violet and neon magenta rim light",
            "dialogue": {"speaker": primary_name, "text_en": "They told us the future was already written."},
        },
        {
            "id": "scene_02_conflict",
            "ordering": 1,
            "time_start_seconds": 3.0,
            "time_end_seconds": 8.0,
            "subject_action": f"{primary_name} notices a glowing quantum signal flickering across the sky",
            "camera_framing": "Medium Shot",
            "camera_movement": "Tracking shot left to right",
            "lighting": "Electric cyber-blue volumetric streetlights",
            "dialogue": {"speaker": primary_name, "text_en": "But signals never lie."},
        },
        {
            "id": "scene_03_action",
            "ordering": 2,
            "time_start_seconds": 8.0,
            "time_end_seconds": 16.0,
            "subject_action": f"{primary_name} sprints across a skybridge, activating wrist tech controls",
            "camera_framing": "Full Body Tracking",
            "camera_movement": "High-speed following camera, smooth gimbal",
            "lighting": "Fast moving neon reflections, deep midnight navy background",
            "dialogue": {"speaker": primary_name, "text_en": "Initiating override sequence."},
        },
        {
            "id": "scene_04_climax",
            "ordering": 3,
            "time_start_seconds": 16.0,
            "time_end_seconds": 24.0,
            "subject_action": f"{', '.join(char_names)} assemble as holographic data manifests before them",
            "camera_framing": "Low-angle heroic two-shot / group shot",
            "camera_movement": "Circular orbiting arc shot",
            "lighting": "Luminous holographic glow, warm soft-white highlights",
            "dialogue": {"speaker": primary_name, "text_en": "Four souls. One universe. We take back the light."},
        },
        {
            "id": "scene_05_resolution",
            "ordering": 4,
            "time_start_seconds": 24.0,
            "time_end_seconds": 30.0,
            "subject_action": f"{primary_name} turns to camera with a confident smile as ZEAZVERSE title reveals",
            "camera_framing": "Cinematic Close-Up",
            "camera_movement": "Slow forward creep and soft fade",
            "lighting": "Subtle twilight purple glow and lens flare",
            "dialogue": {"speaker": primary_name, "text_en": "Welcome to ZEAZVERSE."},
        },
    ]

    scenes = []
    for act in acts:
        pos_prompt = (
            f"Cinematic 9:16 vertical video of {act['subject_action']}, {act['lighting']}, "
            f"photorealistic 8k octane render, dramatic cinematic composition, anime-cyberpunk hybrid aesthetics, "
            f"featuring {primary_name} ({primary_char.get('archetype', 'Hero')})"
        )
        scene = {
            "id": act["id"],
            "ordering": act["ordering"],
            "time_start_seconds": act["time_start_seconds"],
            "time_end_seconds": act["time_end_seconds"],
            "characters": [c.get("id", char_id) for c in (characters if act["id"] == "scene_04_climax" else [primary_char])],
            "character_ref_ids": [f"ref_{c.get('id', char_id)}_turnaround_v1" for c in (characters if act["id"] == "scene_04_climax" else [primary_char])],
            "environment": "Futuristic Cyberpunk Bangkok City 2088",
            "subject_action": act["subject_action"],
            "camera_framing": act["camera_framing"],
            "camera_movement": act["camera_movement"],
            "lighting": act["lighting"],
            "physical_interaction": "Tech interface engagement",
            "dialogue": act["dialogue"],
            "audio": {"music_cue": "synthwave_pulse_128bpm", "sfx": "subtle_cyber_wind_and_activation"},
            "positive_prompt": pos_prompt,
            "negative_prompt": GLOBAL_NEGATIVE_PROMPT,
            "first_frame_continuity": "aligned",
            "last_frame_continuity": "aligned",
            "generation_model": "mock-video-v1",
            "model_settings": {"aspect_ratio": "9:16", "fps": 30, "steps": 30, "cfg_scale": 7.5},
            "expected_output": "1080x1920 MP4 h264 30fps",
            "qa_checks": ["character_identity_verified", "anatomy_checked", "costume_consistent"],
            "status": "pending",
            "output_artifact_uri": "",
        }
        scenes.append(scene)
    return scenes


def generate_youtube_seo_metadata(
    episode: dict[str, Any], characters: list[dict[str, Any]]
) -> dict[str, Any]:
    """Generate YouTube SEO metadata package adhering to AI disclosure and safety."""
    title_base = episode.get("title", "Episode 1")
    char_names = ", ".join([c.get("name", "LALIN") for c in characters]) or "LALIN"

    titles = [
        f"{title_base} | ZEAZVERSE AI Virtual Idol [Shorts]",
        f"Four Souls. One Universe. — {title_base} ft. {char_names}",
        f"{title_base} (Official AI Cinematic Story) | ZEAZVERSE",
    ]

    story_concept = episode.get("story_concept", episode.get("story_concept_json", {}))
    if isinstance(story_concept, str):
        try:
            import json
            story_concept = json.loads(story_concept)
        except (ValueError, TypeError):
            story_concept = {}
    if not isinstance(story_concept, dict):
        story_concept = {}

    description = (
        f"Watch '{title_base}' from ZEAZVERSE!\n\n"
        f"Synopsis: {story_concept.get('synopsis', 'An original AI virtual idol sci-fi cinematic story from Thailand.')}\n\n"
        f"✨ Featured Idols: {char_names}\n"
        f"🌌 Brand: ZEAZVERSE — Four Souls. One Universe.\n"
        f"🇹🇭 Created by ZEAZDEV COMPANY LIMITED\n\n"
        f"🔔 Subscribe to @ZEAZVERSE for weekly original AI cinematic episodes!\n\n"
        f"#ZEAZVERSE #VirtualIdol #AIFilmmaking #SciFi #Cyberpunk #Animation #Bangkok2088 #Shorts\n\n"
        f"--- Synthetic Media Disclosure ---\n"
        f"This video contains AI-generated characters, visuals, and synthetic audio created by ZEAZDEV."
    )

    keywords = [
        "ZEAZVERSE",
        "Virtual Idol",
        "AI Idol Thailand",
        "LALIN",
        "NICHA",
        "PIM",
        "YADA",
        "AI Filmmaking",
        "Sci-Fi Shorts",
        "Cyberpunk Animation",
        "Original Virtual Character",
    ]

    return {
        "candidate_titles": titles,
        "selected_title": titles[0],
        "description": description,
        "keywords": keywords,
        "category_id": "24",  # Entertainment
        "default_language": "en",
        "default_audio_language": "en",
        "self_declared_made_for_kids": False,
        "contains_synthetic_media": True,
        "privacy_status": "private",  # Mandatory private-first
        "embeddable": True,
        "license": "youtube",
        "tags": keywords,
    }


def evaluate_qa_continuity(scenes: list[dict[str, Any]], rendered_manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate storyboard structure and encoded media without claiming visual review."""
    defects = []
    if not scenes:
        defects.append("No scenes defined in storyboard")
    for s in scenes:
        if s.get("time_end_seconds", 0) <= s.get("time_start_seconds", 0):
            defects.append(f"Invalid duration in scene {s.get('id')}")

    media_encoded = rendered_manifest.get("validation_status") == "encoded"
    if not media_encoded:
        defects.append("Rendered media did not pass the encoder validation")
    checks_passed = len(defects) == 0
    return {
        "technical_checks_passed": checks_passed,
        "visual_review_status": "pending",
        "human_visual_review_required": True,
        "media_encoded": media_encoded,
        "defects": defects,
        "notes": "Automated checks cover storyboard timing and media encoding only. Character identity, anatomy, costume, policy, and creative quality require human visual review.",
    }
