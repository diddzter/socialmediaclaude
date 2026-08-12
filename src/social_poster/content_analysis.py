from __future__ import annotations

import base64
import json
import logging
import re
import subprocess
from dataclasses import dataclass

import anthropic

from .config import Settings
from .moods import DEFAULT_MOOD, MOODS

logger = logging.getLogger(__name__)

FRAME_COUNT = 5

ANALYSIS_PROMPT = f"""You are the social media manager for an AI influencer's TikTok/Instagram account.
You're given {FRAME_COUNT} frames sampled evenly across a short vertical video.

Write engaging, on-brand social content for this video and pick the music mood that fits it best.

Respond with ONLY a JSON object, no other text, in this exact shape:
{{
  "caption": "1-3 sentence caption for the post, written in an engaging, first-person influencer voice",
  "hashtags": ["5 to 8 short relevant hashtags, no # symbol, lowercase, no spaces"],
  "overlay_text": "a punchy 3-8 word line to burn onto the video itself, like a title/hook",
  "mood": "exactly one of: {', '.join(MOODS)}"
}}
"""


@dataclass
class ContentAnalysis:
    caption: str
    hashtags: list[str]
    overlay_text: str
    mood: str

    @property
    def full_caption(self) -> str:
        tags = " ".join(f"#{h}" for h in self.hashtags)
        return f"{self.caption}\n\n{tags}".strip()


def _ffprobe_duration(video_path: str) -> float:
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip())


def extract_frames(video_path: str, out_dir: str, count: int = FRAME_COUNT) -> list[str]:
    import os

    os.makedirs(out_dir, exist_ok=True)
    duration = _ffprobe_duration(video_path)
    timestamps = [duration * (i + 1) / (count + 1) for i in range(count)]
    frame_paths = []
    for i, ts in enumerate(timestamps):
        frame_path = os.path.join(out_dir, f"frame_{i}.jpg")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{ts:.2f}",
                "-i",
                video_path,
                "-frames:v",
                "1",
                "-q:v",
                "3",
                frame_path,
            ],
            capture_output=True,
            check=True,
        )
        frame_paths.append(frame_path)
    return frame_paths


def parse_json_block(text: str) -> dict:
    """Pull the first {...} JSON object out of a model response, tolerating markdown fences."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in model response: {text!r}")
    return json.loads(match.group(0))


def analyze_video(video_path: str, settings: Settings, work_dir: str) -> ContentAnalysis:
    frame_paths = extract_frames(video_path, work_dir)

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    content = [{"type": "text", "text": ANALYSIS_PROMPT}]
    for frame_path in frame_paths:
        with open(frame_path, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode("utf-8")
        content.append(
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": data},
            }
        )

    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        messages=[{"role": "user", "content": content}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    parsed = parse_json_block(text)

    mood = str(parsed.get("mood", DEFAULT_MOOD)).strip().lower()
    if mood not in MOODS:
        logger.warning("Model returned unrecognized mood %r, falling back to %r", mood, DEFAULT_MOOD)
        mood = DEFAULT_MOOD

    hashtags = [str(h).lstrip("#").strip().lower() for h in parsed.get("hashtags", []) if str(h).strip()]

    return ContentAnalysis(
        caption=str(parsed.get("caption", "")).strip(),
        hashtags=hashtags,
        overlay_text=str(parsed.get("overlay_text", "")).strip(),
        mood=mood,
    )
