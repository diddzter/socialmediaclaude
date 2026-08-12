from __future__ import annotations

import base64
import io
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from .config import Settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]
VIDEO_MIME_PREFIX = "video/"


@dataclass
class DriveVideo:
    file_id: str
    name: str
    mime_type: str


class DriveClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        creds_json = base64.b64decode(settings.google_service_account_json_b64).decode("utf-8")
        info = json.loads(creds_json)
        credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        self.service = build("drive", "v3", credentials=credentials, cache_discovery=False)

    def list_new_videos(self, limit: int) -> list[DriveVideo]:
        folder_id = self.settings.drive_source_folder_id
        query = f"'{folder_id}' in parents and mimeType contains 'video/' and trashed = false"
        results = []
        page_token = None
        while True:
            response = (
                self.service.files()
                .list(
                    q=query,
                    fields="nextPageToken, files(id, name, mimeType, appProperties)",
                    pageToken=page_token,
                    pageSize=100,
                )
                .execute()
            )
            for f in response.get("files", []):
                props = f.get("appProperties") or {}
                if props.get("posted") == "true":
                    continue
                results.append(DriveVideo(file_id=f["id"], name=f["name"], mime_type=f["mimeType"]))
                if len(results) >= limit:
                    return results
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return results

    def download(self, video: DriveVideo, dest_dir: str) -> str:
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, video.name)
        request = self.service.files().get_media(fileId=video.file_id)
        with io.FileIO(dest_path, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        return dest_path

    def upload_public(self, local_path: str, name: str) -> str:
        """Upload a processed video to the processed folder and return a publicly fetchable URL."""
        folder_id = self.settings.drive_processed_folder_id
        file_metadata = {"name": name, "parents": [folder_id]}
        media = MediaFileUpload(local_path, mimetype="video/mp4", resumable=True)
        uploaded = self.service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        file_id = uploaded["id"]
        self.service.permissions().create(
            fileId=file_id, body={"type": "anyone", "role": "reader"}
        ).execute()
        return f"https://drive.google.com/uc?export=download&id={file_id}"

    def mark_processed(self, video: DriveVideo, results: dict[str, bool]) -> None:
        props = {
            "posted": "true",
            "posted_at": datetime.now(timezone.utc).isoformat(),
        }
        for platform, ok in results.items():
            props[f"posted_{platform}"] = "true" if ok else "false"
        self.service.files().update(fileId=video.file_id, body={"appProperties": props}).execute()
