"""Facebook uploader — draft-mode placeholder.

No Facebook Page ID/access-token config exists in this project yet (config.py
only has IG_ACCOUNT_ID — Instagram's Business Account, not a Facebook Page).
Until that config surface is added, every upload is recorded as a draft so
Publisher's caller never has to special-case "no Facebook integration yet"
itself — swap this stub's upload() body for a real Graph API
POST /{page_id}/videos call (same GRAPH_URL family as
src/core/instagram_poster.py) once a Page ID/token are available.
"""
from __future__ import annotations

from pathlib import Path

from src.core.uploaders.base import UploadResult


class FacebookUploader:
    def upload(self, video_path: str | Path, caption: str, config: dict) -> UploadResult:
        return UploadResult(
            status="draft",
            note="Facebook publishing not yet connected — no Page ID/access token "
                 "configured. Video saved locally; upload manually, or wire up a "
                 "Graph API POST /{page_id}/videos call with a Page access token.",
        )
