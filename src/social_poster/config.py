from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    val = os.environ.get(name)
    return int(val) if val else default


def _float(name: str, default: float) -> float:
    val = os.environ.get(name)
    return float(val) if val else default


@dataclass
class Settings:
    # Google Drive
    google_service_account_json_b64: str = field(default_factory=lambda: os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_BASE64", ""))
    drive_source_folder_id: str = field(default_factory=lambda: os.environ.get("DRIVE_SOURCE_FOLDER_ID", ""))
    drive_processed_folder_id: str = field(default_factory=lambda: os.environ.get("DRIVE_PROCESSED_FOLDER_ID", ""))

    # Anthropic (content analysis: caption, hashtags, mood)
    anthropic_api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    anthropic_model: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"))

    # Instagram (Meta Graph API)
    enable_instagram: bool = field(default_factory=lambda: _bool("ENABLE_INSTAGRAM", True))
    ig_business_account_id: str = field(default_factory=lambda: os.environ.get("IG_BUSINESS_ACCOUNT_ID", ""))
    ig_access_token: str = field(default_factory=lambda: os.environ.get("IG_ACCESS_TOKEN", ""))
    ig_graph_api_version: str = field(default_factory=lambda: os.environ.get("IG_GRAPH_API_VERSION", "v21.0"))

    # TikTok (Content Posting API)
    enable_tiktok: bool = field(default_factory=lambda: _bool("ENABLE_TIKTOK", True))
    tiktok_client_key: str = field(default_factory=lambda: os.environ.get("TIKTOK_CLIENT_KEY", ""))
    tiktok_client_secret: str = field(default_factory=lambda: os.environ.get("TIKTOK_CLIENT_SECRET", ""))
    tiktok_access_token: str = field(default_factory=lambda: os.environ.get("TIKTOK_ACCESS_TOKEN", ""))
    tiktok_refresh_token: str = field(default_factory=lambda: os.environ.get("TIKTOK_REFRESH_TOKEN", ""))
    tiktok_privacy_level: str = field(default_factory=lambda: os.environ.get("TIKTOK_PRIVACY_LEVEL", "SELF_ONLY"))

    # Pipeline behavior
    max_videos_per_run: int = field(default_factory=lambda: _int("MAX_VIDEOS_PER_RUN", 1))
    dry_run: bool = field(default_factory=lambda: _bool("DRY_RUN", False))
    work_dir: str = field(default_factory=lambda: os.environ.get("WORK_DIR", "/tmp/social_poster"))

    # Video editing
    music_library_path: str = field(default_factory=lambda: os.environ.get("MUSIC_LIBRARY_PATH", "music_library/library.json"))
    music_volume: float = field(default_factory=lambda: _float("MUSIC_VOLUME", 0.25))
    font_file: str = field(default_factory=lambda: os.environ.get("FONT_FILE", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))

    def validate_for_drive(self) -> None:
        missing = [
            name
            for name, val in (
                ("GOOGLE_SERVICE_ACCOUNT_JSON_BASE64", self.google_service_account_json_b64),
                ("DRIVE_SOURCE_FOLDER_ID", self.drive_source_folder_id),
            )
            if not val
        ]
        if missing:
            raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    def validate_for_instagram(self) -> None:
        if not self.enable_instagram:
            return
        missing = [
            name
            for name, val in (
                ("IG_BUSINESS_ACCOUNT_ID", self.ig_business_account_id),
                ("IG_ACCESS_TOKEN", self.ig_access_token),
                ("DRIVE_PROCESSED_FOLDER_ID", self.drive_processed_folder_id),
            )
            if not val
        ]
        if missing:
            raise RuntimeError(f"Missing required env vars for Instagram: {', '.join(missing)}")

    def validate_for_tiktok(self) -> None:
        if not self.enable_tiktok:
            return
        if not self.tiktok_access_token and not (self.tiktok_client_key and self.tiktok_client_secret and self.tiktok_refresh_token):
            raise RuntimeError(
                "TikTok needs either TIKTOK_ACCESS_TOKEN, or TIKTOK_CLIENT_KEY + "
                "TIKTOK_CLIENT_SECRET + TIKTOK_REFRESH_TOKEN so it can mint a fresh one."
            )
