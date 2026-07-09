"""Instagram uploader — thin adapter over src.core.instagram_poster's real
Meta Graph API reel-publishing flow, conforming to the Uploader protocol.

config keys required: ig_account_id, access_token, cloudinary_config
(the same dict shape pipeline.py already builds for post_reel_to_instagram).
config["cover_path"] is optional.
"""
from __future__ import annotations

from pathlib import Path

from src.core.instagram_poster import post_reel_to_instagram
from src.core.uploaders.base import UploadResult


class InstagramUploader:
    def upload(self, video_path: str | Path, caption: str, config: dict) -> UploadResult:
        try:
            post_id = post_reel_to_instagram(
                video_path=video_path,
                caption=caption,
                ig_account_id=config["ig_account_id"],
                access_token=config["access_token"],
                cloudinary_config=config["cloudinary_config"],
                cover_path=config.get("cover_path"),
            )
        except KeyError as exc:
            return UploadResult(status="failed", error=f"missing config key: {exc}")
        except Exception as exc:
            return UploadResult(status="failed", error=str(exc))

        return UploadResult(
            status="published",
            post_id=post_id,
            post_url=f"https://www.instagram.com/p/{post_id}/",
        )
