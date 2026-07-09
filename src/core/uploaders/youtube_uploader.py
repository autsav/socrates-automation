"""YouTube uploader — draft-mode placeholder.

No OAuth/browser-session infra exists in this project yet (agent-content-kit's
equivalent uses a Playwright browser session, falling back to the YouTube
Data API via OAuth). Until one of those is wired up here, every upload is
recorded as a draft so Publisher's caller never has to special-case "no
YouTube integration yet" itself — swap this stub's upload() body for a real
google-api-python-client call (or a Playwright uploader) once that infra
exists.
"""
from __future__ import annotations

from pathlib import Path

from src.core.uploaders.base import UploadResult


class YouTubeUploader:
    def upload(self, video_path: str | Path, caption: str, config: dict) -> UploadResult:
        return UploadResult(
            status="draft",
            note="YouTube publishing not yet connected — no OAuth credentials "
                 "configured. Video saved locally; upload manually, or wire up "
                 "google-api-python-client with a YouTube Data API OAuth client.",
        )
