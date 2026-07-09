"""Multi-platform publisher — cross-posts one rendered video to N platforms
through a common Uploader interface, so pipeline.py/team/ never has to hold
one bespoke branch of upload logic per platform.

Only Instagram has a real API integration today (src.core.uploaders.
instagram_uploader wraps the existing Meta Graph API flow in
src/core/instagram_poster.py); YouTube, TikTok, and Facebook are draft-mode
placeholders (see their uploader modules) pending OAuth/browser-session infra
this project doesn't have yet. Publish still records a result for every
requested platform, so adding a real integration later is a drop-in Uploader
swap rather than a Publisher rewrite.
"""
from __future__ import annotations

import logging
from pathlib import Path

from src.core.uploaders.base import UploadResult, Uploader
from src.core.uploaders.instagram_uploader import InstagramUploader
from src.core.uploaders.youtube_uploader import YouTubeUploader
from src.core.uploaders.tiktok_uploader import TikTokUploader
from src.core.uploaders.facebook_uploader import FacebookUploader

logger = logging.getLogger("core.publisher")


def default_uploaders() -> dict[str, Uploader]:
    return {
        "instagram": InstagramUploader(),
        "youtube": YouTubeUploader(),
        "tiktok": TikTokUploader(),
        "facebook": FacebookUploader(),
    }


class Publisher:
    def __init__(self, uploaders: dict[str, Uploader] | None = None):
        self.uploaders = uploaders if uploaders is not None else default_uploaders()

    def publish(
        self,
        platforms: list[str],
        video_path: str | Path,
        caption: str,
        configs: dict[str, dict] | None = None,
    ) -> list[dict]:
        """Publish video_path/caption to every platform in `platforms`.

        `configs` maps platform name -> that platform's own credentials/config
        dict, e.g. {"instagram": {"ig_account_id": ..., "access_token": ...,
        "cloudinary_config": ...}}. Returns one result dict per platform:
        {"platform": ..., **UploadResult.to_dict()}. Never raises — a single
        platform's failure is recorded, not propagated, so one bad platform
        can't block publishing to the others.
        """
        configs = configs or {}
        results = []

        for platform in platforms:
            uploader = self.uploaders.get(platform)
            if uploader is None:
                logger.warning("Unknown platform: %s", platform)
                result = UploadResult(status="skipped", note=f"Unknown platform: {platform}")
                results.append({"platform": platform, **result.to_dict()})
                continue

            try:
                result = uploader.upload(video_path, caption, configs.get(platform, {}))
            except Exception as exc:
                logger.error("Publish to %s failed: %s", platform, exc)
                result = UploadResult(status="failed", error=str(exc))

            results.append({"platform": platform, **result.to_dict()})

        published = sum(1 for r in results if r["status"] == "published")
        logger.info("Published %d/%d platform(s)", published, len(results))
        return results
