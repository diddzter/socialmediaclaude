from __future__ import annotations

import logging
import os
import shutil
import uuid

from . import video_editor
from .config import Settings
from .content_analysis import analyze_video
from .drive_client import DriveClient, DriveVideo
from .music_library import MusicLibrary
from .publishers import instagram, tiktok

logger = logging.getLogger(__name__)


def process_one_video(
    drive: DriveClient,
    music_library: MusicLibrary,
    video: DriveVideo,
    settings: Settings,
) -> dict[str, bool]:
    run_dir = os.path.join(settings.work_dir, uuid.uuid4().hex)
    os.makedirs(run_dir, exist_ok=True)
    try:
        logger.info("Downloading %s", video.name)
        local_path = drive.download(video, run_dir)

        logger.info("Analyzing content for %s", video.name)
        analysis = analyze_video(local_path, settings, work_dir=run_dir)
        logger.info("Caption: %s | mood: %s", analysis.caption, analysis.mood)

        track = music_library.pick_track(analysis.mood)
        logger.info("Picked track: %s", track.path)

        output_path = os.path.join(run_dir, "output.mp4")
        video_editor.render(
            video_path=local_path,
            overlay_text=analysis.overlay_text,
            music_path=track.path,
            output_path=output_path,
            font_file=settings.font_file,
            music_volume=settings.music_volume,
        )

        results: dict[str, bool] = {}

        if settings.dry_run:
            logger.info("[dry-run] Skipping publish for %s. Caption:\n%s", video.name, analysis.full_caption)
            return results

        if settings.enable_instagram:
            try:
                public_url = drive.upload_public(output_path, name=f"processed_{video.name}")
                media_id = instagram.publish(public_url, analysis.full_caption, settings)
                logger.info("Published to Instagram: %s", media_id)
                results["instagram"] = True
            except Exception:
                logger.exception("Instagram publish failed for %s", video.name)
                results["instagram"] = False

        if settings.enable_tiktok:
            try:
                publish_id = tiktok.publish(output_path, analysis.full_caption, settings)
                logger.info("Published to TikTok: %s", publish_id)
                results["tiktok"] = True
            except Exception:
                logger.exception("TikTok publish failed for %s", video.name)
                results["tiktok"] = False

        if results and any(results.values()):
            drive.mark_processed(video, results)
        elif results:
            logger.warning("All platforms failed for %s; leaving unmarked so it's retried next run.", video.name)

        return results
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def run(settings: Settings) -> list[dict[str, bool]]:
    settings.validate_for_drive()
    settings.validate_for_instagram()
    settings.validate_for_tiktok()

    drive = DriveClient(settings)
    music_library = MusicLibrary(settings.music_library_path)

    videos = drive.list_new_videos(limit=settings.max_videos_per_run)
    logger.info("Found %d new video(s) to process", len(videos))

    summary = []
    for video in videos:
        summary.append(process_one_video(drive, music_library, video, settings))
    return summary
