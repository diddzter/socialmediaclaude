from __future__ import annotations

import json
import logging
import os
import random
from dataclasses import dataclass

from .moods import DEFAULT_MOOD

logger = logging.getLogger(__name__)


@dataclass
class Track:
    path: str
    credit: str = ""


class MusicLibrary:
    def __init__(self, manifest_path: str):
        self.manifest_path = manifest_path
        self.base_dir = os.path.dirname(os.path.abspath(manifest_path))
        if not os.path.exists(manifest_path):
            raise FileNotFoundError(
                f"Music library manifest not found at {manifest_path}. "
                "Copy music_library/library.example.json to music_library/library.json "
                "and add your own royalty-free tracks (see README)."
            )
        with open(manifest_path, "r", encoding="utf-8") as f:
            self._data: dict[str, list[dict]] = json.load(f)

    def pick_track(self, mood: str) -> Track:
        entries = self._data.get(mood) or self._data.get(DEFAULT_MOOD) or []
        if not entries:
            raise ValueError(
                f"No tracks configured for mood '{mood}' (and no '{DEFAULT_MOOD}' fallback either) "
                f"in {self.manifest_path}."
            )
        chosen = random.choice(entries)
        track_path = chosen["file"]
        if not os.path.isabs(track_path):
            track_path = os.path.join(self.base_dir, track_path)
        if not os.path.exists(track_path):
            raise FileNotFoundError(f"Music file listed in manifest does not exist: {track_path}")
        return Track(path=track_path, credit=chosen.get("credit", ""))
