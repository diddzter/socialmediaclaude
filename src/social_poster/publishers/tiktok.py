from __future__ import annotations

import logging
import os
import time

import requests

from ..config import Settings

logger = logging.getLogger(__name__)

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"

CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 300


class TikTokPublishError(RuntimeError):
    pass


def _get_access_token(settings: Settings) -> str:
    """Use TIKTOK_ACCESS_TOKEN as-is if set, otherwise mint one from the refresh token.

    TikTok access tokens are short-lived (~24h), so in a scheduled/CI context the
    refresh-token path is the one that actually works run over run. Note TikTok
    rotates the refresh token on every use -- if you see auth failures after this
    has run a few times, update the TIKTOK_REFRESH_TOKEN secret from the logged
    warning below.
    """
    if settings.tiktok_access_token:
        return settings.tiktok_access_token

    resp = requests.post(
        TOKEN_URL,
        data={
            "client_key": settings.tiktok_client_key,
            "client_secret": settings.tiktok_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": settings.tiktok_refresh_token,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    new_refresh_token = payload.get("refresh_token")
    if new_refresh_token and new_refresh_token != settings.tiktok_refresh_token:
        logger.warning(
            "TikTok rotated the refresh token. Update the TIKTOK_REFRESH_TOKEN secret to: %s "
            "(the old one is now invalid).",
            new_refresh_token,
        )
    return payload["access_token"]


def _chunk_plan(video_size: int) -> tuple[int, int]:
    if video_size <= CHUNK_SIZE:
        return video_size, 1
    total_chunks = (video_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    return CHUNK_SIZE, total_chunks


def publish(video_path: str, caption: str, settings: Settings) -> str:
    access_token = _get_access_token(settings)
    video_size = os.path.getsize(video_path)
    chunk_size, total_chunks = _chunk_plan(video_size)

    init_resp = requests.post(
        INIT_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json={
            "post_info": {
                "title": caption,
                "privacy_level": settings.tiktok_privacy_level,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks,
            },
        },
        timeout=60,
    )
    init_resp.raise_for_status()
    init_payload = init_resp.json()
    if init_payload.get("error", {}).get("code") not in (None, "ok"):
        raise TikTokPublishError(f"TikTok init failed: {init_payload['error']}")

    publish_id = init_payload["data"]["publish_id"]
    upload_url = init_payload["data"]["upload_url"]

    with open(video_path, "rb") as f:
        for chunk_index in range(total_chunks):
            start = chunk_index * chunk_size
            f.seek(start)
            data = f.read(chunk_size)
            end = start + len(data) - 1
            upload_resp = requests.put(
                upload_url,
                data=data,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Range": f"bytes {start}-{end}/{video_size}",
                },
                timeout=120,
            )
            upload_resp.raise_for_status()

    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        status_resp = requests.post(
            STATUS_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            json={"publish_id": publish_id},
            timeout=30,
        )
        status_resp.raise_for_status()
        status_payload = status_resp.json()
        status = status_payload.get("data", {}).get("status")
        if status == "PUBLISH_COMPLETE":
            break
        if status == "FAILED":
            raise TikTokPublishError(f"TikTok reported publish failure: {status_payload}")
        time.sleep(POLL_INTERVAL_SECONDS)
    else:
        logger.warning(
            "Timed out waiting for TikTok publish status for %s; it may still complete asynchronously.",
            publish_id,
        )

    return publish_id
