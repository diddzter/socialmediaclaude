import json
import os

import pytest

from social_poster.music_library import MusicLibrary


def _write_manifest(tmp_path, data):
    manifest_path = tmp_path / "library.json"
    manifest_path.write_text(json.dumps(data))
    return str(manifest_path)


def _touch(tmp_path, name):
    path = tmp_path / name
    path.write_bytes(b"fake-mp3-bytes")
    return path


def test_pick_track_for_known_mood(tmp_path):
    _touch(tmp_path, "chill_1.mp3")
    manifest = _write_manifest(tmp_path, {"chill": [{"file": "chill_1.mp3", "credit": "x"}]})

    lib = MusicLibrary(manifest)
    track = lib.pick_track("chill")

    assert track.path == str(tmp_path / "chill_1.mp3")
    assert track.credit == "x"


def test_pick_track_falls_back_to_default_mood(tmp_path):
    _touch(tmp_path, "chill_1.mp3")
    manifest = _write_manifest(tmp_path, {"chill": [{"file": "chill_1.mp3"}]})

    lib = MusicLibrary(manifest)
    track = lib.pick_track("dramatic")  # not present, should fall back to chill

    assert track.path == str(tmp_path / "chill_1.mp3")


def test_pick_track_raises_when_no_tracks_available(tmp_path):
    manifest = _write_manifest(tmp_path, {"chill": []})
    lib = MusicLibrary(manifest)

    with pytest.raises(ValueError):
        lib.pick_track("dramatic")


def test_pick_track_raises_when_file_missing(tmp_path):
    manifest = _write_manifest(tmp_path, {"chill": [{"file": "does_not_exist.mp3"}]})
    lib = MusicLibrary(manifest)

    with pytest.raises(FileNotFoundError):
        lib.pick_track("chill")


def test_missing_manifest_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        MusicLibrary(str(tmp_path / "nope.json"))
