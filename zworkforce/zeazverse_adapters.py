"""Pluggable AI model provider adapters and rendering pipeline for ZEAZVERSE."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any


class ZeazverseProviderError(RuntimeError):
    """Raised when an AI provider fails or is unconfigured."""


class BaseProviderAdapter:
    """Base class for all ZEAZVERSE provider adapters."""

    def __init__(self, name: str, mock: bool = True):
        self.name = name
        self.mock = mock

    def is_available(self) -> bool:
        return True


class MockImageProviderAdapter(BaseProviderAdapter):
    """Generates synthetic reference frames and concept artwork."""

    def __init__(self):
        super().__init__("mock-image-adapter", mock=True)

    def generate_image(
        self, prompt: str, negative_prompt: str, reference_ids: list[str], parameters: dict[str, Any]
    ) -> dict[str, Any]:
        artifact_id = f"art_img_{uuid.uuid4().hex[:12]}"
        simulated_hash = hashlib.sha256(f"{prompt}:{','.join(reference_ids)}".encode("utf-8")).hexdigest()
        return {
            "artifact_id": artifact_id,
            "status": "succeeded",
            "storage_uri": f"storage://zeazverse/images/{artifact_id}.png",
            "sha256": simulated_hash,
            "width": 1080,
            "height": 1920,
            "provider": self.name,
            "cost_credits": 0.05,
        }


class MockVideoProviderAdapter(BaseProviderAdapter):
    """Simulates video generation for scene prompts."""

    def __init__(self):
        super().__init__("mock-video-adapter", mock=True)

    def generate_video_clip(
        self,
        scene_id: str,
        prompt: str,
        negative_prompt: str,
        duration_seconds: float,
        character_refs: list[str],
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        job_id = f"job_vid_{uuid.uuid4().hex[:12]}"
        clip_hash = hashlib.sha256(f"{scene_id}:{prompt}:{duration_seconds}".encode("utf-8")).hexdigest()
        return {
            "job_id": job_id,
            "scene_id": scene_id,
            "status": "succeeded",
            "output_uri": f"storage://zeazverse/video_clips/{scene_id}_{job_id[:8]}.mp4",
            "sha256": clip_hash,
            "duration_seconds": duration_seconds,
            "fps": 30,
            "resolution": "1080x1920",
            "cost_credits": round(duration_seconds * 0.10, 2),
            "provider": self.name,
        }


class MockAudioProviderAdapter(BaseProviderAdapter):
    """Synthesizes original Thai-accented English speech and background score."""

    def __init__(self):
        super().__init__("mock-audio-adapter", mock=True)

    def synthesize_speech(self, text: str, voice_profile: dict[str, Any]) -> dict[str, Any]:
        audio_id = f"aud_speech_{uuid.uuid4().hex[:12]}"
        sha = hashlib.sha256(f"{text}:{voice_profile.get('model')}".encode("utf-8")).hexdigest()
        return {
            "audio_id": audio_id,
            "status": "succeeded",
            "storage_uri": f"storage://zeazverse/audio/{audio_id}.wav",
            "sha256": sha,
            "duration_seconds": max(1.0, len(text.split()) * 0.4),
            "cost_credits": 0.02,
        }


class VideoEditingPipeline:
    """Create an honest, offline synthetic storyboard sample with FFmpeg."""

    MAX_SCENES = 30
    MAX_DURATION_SECONDS = 300.0
    COLORS = ("0x160D2B", "0x10202C", "0x17142F", "0x2B102D", "0x07152A")

    def __init__(self, output_dir: str | Path = "/tmp/zeazverse/renders"):
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _vtt_timestamp(seconds: float) -> str:
        millis = round(seconds * 1000)
        hours, millis = divmod(millis, 3_600_000)
        minutes, millis = divmod(millis, 60_000)
        whole_seconds, millis = divmod(millis, 1000)
        return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{millis:03d}"

    @staticmethod
    def _caption(scene: dict[str, Any]) -> str:
        dialogue = scene.get("dialogue")
        if dialogue is None:
            dialogue = scene.get("dialogue_json")
        if isinstance(dialogue, str):
            try:
                import json
                dialogue = json.loads(dialogue)
            except (ValueError, TypeError):
                dialogue = {}
        if not isinstance(dialogue, dict):
            return ""
        text = dialogue.get("text_en") or dialogue.get("text") or ""
        return re.sub(r"[\r\n]+", " ", str(text)).replace("-->", "—>").strip()[:500]

    def render_episode(
        self,
        episode_id: str,
        scenes: list[dict[str, Any]],
        seo_metadata: dict[str, Any],
        subtitles_srt: str | None = None,
    ) -> dict[str, Any]:
        """Render a real MP4 of abstract scene cards and dialogue captions.

        This is a technical sample only: it does not generate idol imagery,
        animation, voice, or music and must not be treated as a finished episode.
        """
        if not isinstance(scenes, list) or not scenes or len(scenes) > self.MAX_SCENES:
            raise ZeazverseProviderError(f"render requires 1..{self.MAX_SCENES} scenes")
        normalized = []
        for scene in sorted(scenes, key=lambda item: float(item.get("time_start_seconds", 0))):
            start = float(scene.get("time_start_seconds", 0))
            end = float(scene.get("time_end_seconds", 0))
            if start < 0 or end <= start:
                raise ZeazverseProviderError("render scene time range is invalid")
            normalized.append((scene, start, end))
        total_duration = max(end for _, _, end in normalized)
        if total_duration > self.MAX_DURATION_SECONDS:
            raise ZeazverseProviderError("render exceeds the 300 second limit")
        previous_end = 0.0
        for _, start, end in normalized:
            if abs(start - previous_end) > 0.001:
                raise ZeazverseProviderError("render scenes must be contiguous and start at zero")
            previous_end = end

        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            raise ZeazverseProviderError("FFmpeg is required to render a valid MP4 sample")
        render_id = f"render_{uuid.uuid4().hex[:12]}"
        safe_episode_id = re.sub(r"[^a-zA-Z0-9_-]", "_", episode_id)[:80] or "episode"
        target_mp4 = self.output_dir / f"{safe_episode_id}_{render_id}.mp4"
        target_vtt = self.output_dir / f"{safe_episode_id}_{render_id}.vtt"
        temporary_mp4 = target_mp4.with_name(f"{target_mp4.stem}.tmp.mp4")

        command = [ffmpeg_bin, "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
        filters = []
        for index, (_, start, end) in enumerate(normalized):
            duration = end - start
            color = self.COLORS[index % len(self.COLORS)]
            command.extend(["-f", "lavfi", "-i", f"color=c={color}:s=720x1280:r=30:d={duration:.3f}"])
            filters.append(f"[{index}:v]setpts=PTS-STARTPTS[v{index}]")
        audio_index = len(normalized)
        command.extend(["-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={total_duration:.3f}"])
        concat_inputs = "".join(f"[v{i}]" for i in range(len(normalized)))
        filters.append(f"{concat_inputs}concat=n={len(normalized)}:v=1:a=0,format=yuv420p[vout]")
        command.extend([
            "-filter_complex", ";".join(filters), "-map", "[vout]", "-map", f"{audio_index}:a:0",
            "-t", f"{total_duration:.3f}", "-r", "30", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "28", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", str(temporary_mp4),
        ])
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=180)
            if not temporary_mp4.is_file() or temporary_mp4.stat().st_size < 1024:
                raise ZeazverseProviderError("FFmpeg returned without a usable media file")
            temporary_mp4.replace(target_mp4)
        except (subprocess.SubprocessError, OSError) as exc:
            temporary_mp4.unlink(missing_ok=True)
            raise ZeazverseProviderError("FFmpeg failed to produce the MP4 sample") from exc

        cues = []
        for scene, start, end in normalized:
            caption = self._caption(scene)
            if caption:
                cues.append(f"{self._vtt_timestamp(start)} --> {self._vtt_timestamp(end)}\n{caption}")
        target_vtt.write_text("WEBVTT\n\n" + "\n\n".join(cues) + ("\n" if cues else ""), encoding="utf-8")
        digest = hashlib.sha256(target_mp4.read_bytes()).hexdigest()

        return {
            "render_id": render_id,
            "status": "synthetic_sample",
            "render_kind": "abstract_storyboard_sample",
            "provider": "ffmpeg_local",
            "external_media_generated": False,
            "output_video_uri": str(target_mp4),
            "output_sha256": digest,
            "subtitles_vtt_uri": str(target_vtt),
            "duration_seconds": total_duration,
            "format": "720x1280",
            "fps": 30,
            "codec": "h264",
            "audio_codec": "aac",
            "validation_status": "encoded",
            "visual_review_required": True,
            "validation_report": {
                "media_check": "ffmpeg_exit_zero_and_nonempty_file",
                "width": 720,
                "height": 1280,
                "aspect_ratio": "9:16",
                "fps": 30,
                "video_stream": "h264",
                "audio_stream": "aac_stereo_silence",
            },
        }
