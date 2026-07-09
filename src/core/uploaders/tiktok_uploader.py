"""TikTok uploader — draft-mode placeholder.

No OAuth/browser-session infra exists in this project yet (agent-content-kit's
equivalent uses a Playwright browser session, falling back to TikTok's
Content Posting API via OAuth). Until one of those is wired up here, every
upload is recorded as a draft so Publisher's caller never has to
special-case "no TikTok integration yet" itself — swap this stub's upload()
body for a real Content Posting API call (or a Playwright uploader) once
that infra exists.
"""
from __future__ import annotations

from pathlib import Path

from src.core.uploaders.base import UploadResult


class TikTokUploader:
    def upload(self, video_path: str | Path, caption: str, config: dict) -> UploadResult:
        return UploadResult(
            status="draft",
            note="TikTok publishing not yet connected — no OAuth credentials "
                 "configured. Video saved locally; upload manually, or wire up "
                 "TikTok's Content Posting API with an OAuth client.",
        )
