from __future__ import annotations

import logging
import os
import subprocess
import textwrap

logger = logging.getLogger(__name__)

MAX_CHARS_PER_LINE = 22


def wrap_overlay_text(text: str, max_chars: int = MAX_CHARS_PER_LINE) -> str:
    """Wrap a short overlay line to a few lines so it fits a vertical video without spilling off-screen."""
    text = " ".join(text.split())
    if not text:
        return ""
    lines = textwrap.wrap(text, width=max_chars, break_long_words=False)
    return "\n".join(lines)


def _has_audio_stream(video_path: str) -> bool:
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            video_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(out.stdout.strip())


def render(
    video_path: str,
    overlay_text: str,
    music_path: str,
    output_path: str,
    font_file: str,
    music_volume: float = 0.25,
) -> str:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    wrapped = wrap_overlay_text(overlay_text)
    textfile_path = output_path + ".overlay.txt"
    with open(textfile_path, "w", encoding="utf-8") as f:
        f.write(wrapped)

    has_audio = _has_audio_stream(video_path)

    def esc(path: str) -> str:
        return path.replace("\\", "/").replace(":", "\\:")

    drawtext = (
        f"drawtext=fontfile='{esc(font_file)}':textfile='{esc(textfile_path)}':"
        "fontsize=64:fontcolor=white:line_spacing=10:"
        "box=1:boxcolor=black@0.55:boxborderw=20:"
        "x=(w-text_w)/2:y=h-th-140"
    )

    if has_audio:
        filter_complex = (
            f"[0:v]{drawtext}[vout];"
            f"[1:a]volume={music_volume}[music];"
            f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
    else:
        filter_complex = f"[0:v]{drawtext}[vout];[1:a]volume={music_volume}[aout]"

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-stream_loop",
        "-1",
        "-i",
        music_path,
        "-filter_complex",
        filter_complex,
        "-map",
        "[vout]",
        "-map",
        "[aout]",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-shortest",
        output_path,
    ]

    logger.info("Rendering video: %s", " ".join(cmd))
    subprocess.run(cmd, capture_output=True, check=True)
    os.remove(textfile_path)
    return output_path
