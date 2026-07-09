"""Common uploader interface + result type for src/core/publisher.py.

Every platform uploader implements upload(video_path, caption, config) ->
UploadResult, so Publisher can treat every platform identically regardless of
whether that platform has a real API integration (Instagram) or is still
draft-mode-only pending OAuth/browser-session infra this project doesn't have
yet (YouTube, TikTok, Facebook) — mirroring agent-content-kit's PublisherAgent
priority chain (real upload -> draft placeholder) without its Playwright/
OAuth dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal, Protocol

Status = Literal["published", "draft", "failed", "skipped"]


@dataclass
class UploadResult:
    status: Status
    post_id: str | None = None
    post_url: str | None = None
    note: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class Uploader(Protocol):
    def upload(self, video_path: str | Path, caption: str, config: dict) -> UploadResult:
        ...
