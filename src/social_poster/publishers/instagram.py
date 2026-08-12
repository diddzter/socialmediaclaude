from __future__ import annotations

import logging
import time

import requests

from ..config import Settings

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 300


class InstagramPublishError(RuntimeError):
    pass


def _base_url(settings: Settings) -> str:
    return f"https://graph.facebook.com/{settings.ig_graph_api_version}"


def publish(video_url: str, caption: str, settings: Settings) -> str:
    """Publish a Reel from a publicly-fetchable video URL. Returns the published media id."""
    base = _base_url(settings)

    create_resp = requests.post(
        f"{base}/{settings.ig_business_account_id}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": settings.ig_access_token,
        },
        timeout=60,
    )
    create_resp.raise_for_status()
    container_id = create_resp.json()["id"]

    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        status_resp = requests.get(
            f"{base}/{container_id}",
            params={"fields": "status_code,status", "access_token": settings.ig_access_token},
            timeout=30,
        )
        status_resp.raise_for_status()
        payload = status_resp.json()
        status_code = payload.get("status_code")
        if status_code == "FINISHED":
            break
        if status_code == "ERROR":
            raise InstagramPublishError(f"Instagram failed to process video container: {payload}")
        time.sleep(POLL_INTERVAL_SECONDS)
    else:
        raise InstagramPublishError("Timed out waiting for Instagram to finish processing the video container")

    publish_resp = requests.post(
        f"{base}/{settings.ig_business_account_id}/media_publish",
        data={"creation_id": container_id, "access_token": settings.ig_access_token},
        timeout=60,
    )
    publish_resp.raise_for_status()
    return publish_resp.json()["id"]
