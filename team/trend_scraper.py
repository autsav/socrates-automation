"""Trend Scraper agent — fetches trending hashtags & sounds from TikTok's
public Creative Center API.

Unlike the other team/ agents, this one calls no LLM: it's a thin HTTP
scraper, so team/base_agent.py's BaseAgent (whose call_with_retry is shaped
around self.client.call(role, ..., schema)) doesn't fit — this class has its
own small retry/backoff loop around requests.get instead, and degrades to a
static hashtag fallback (rather than raising) when TikTok's API is
unreachable, since a network blip here should never be fatal.

Not yet wired into team/orchestrator.py — this agent's output (a TrendReport)
is intended to eventually ground team/planner.py's hashtag/audio choices in
what's actually trending, per .claude/integration-research-plan.md Phase 2
item 6.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import requests

from team.models import TrendReport

logger = logging.getLogger("team.agent.TrendScraperAgent")

_CREATIVE_CENTER_API = "https://ads.tiktok.com/creative_radar_api/v1/popular"
_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"

_FALLBACK_HASHTAGS = [
    {"name": "fyp", "views": 0, "posts": 0, "trend": 1},
    {"name": "viral", "views": 0, "posts": 0, "trend": 1},
    {"name": "trending", "views": 0, "posts": 0, "trend": 1},
]


class TrendScraperAgent:
    max_retries = 3
    retry_delay = 1.5
    is_critical = False

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def run(self, niche: str = "", country: str = "US") -> TrendReport:
        hashtags = self._fetch_with_retry(
            f"{_CREATIVE_CENTER_API}/hashtag/list/", country,
            self._parse_hashtags, self._fallback_hashtags(niche),
        )
        sounds = self._fetch_with_retry(
            f"{_CREATIVE_CENTER_API}/music/list/", country,
            self._parse_sounds, [],
        )
        return TrendReport(
            niche=niche,
            hashtags=hashtags,
            sounds=sounds,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    def _fetch_with_retry(self, url: str, country: str, parse_fn, fallback: list[dict]) -> list[dict]:
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(
                    url,
                    params={"page": 1, "limit": 20, "period": 7,
                            "country_code": country, "sort_by": "popular"},
                    headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
                    timeout=15,
                )
                resp.raise_for_status()
                return parse_fn(resp.json())
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "trend fetch %s attempt %d/%d failed: %s: %s",
                    url, attempt, self.max_retries, type(exc).__name__, exc,
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * (2 ** (attempt - 1)))
        logger.warning("trend fetch %s exhausted retries (%s) — using fallback", url, last_exc)
        return fallback

    def _parse_hashtags(self, data: dict) -> list[dict]:
        items = data.get("data", {}).get("list", [])
        return [
            {
                "name": item.get("hashtag_name", ""),
                "views": item.get("video_views", 0),
                "posts": item.get("publish_cnt", 0),
                "trend": item.get("trend", 0),
            }
            for item in items[:15]
        ]

    def _parse_sounds(self, data: dict) -> list[dict]:
        items = data.get("data", {}).get("list", [])
        return [
            {
                "title": item.get("title", ""),
                "author": item.get("author", ""),
                "usage_count": item.get("video_cnt", 0),
            }
            for item in items[:10]
        ]

    def _fallback_hashtags(self, niche: str) -> list[dict]:
        base = list(_FALLBACK_HASHTAGS)
        if niche:
            base.insert(0, {"name": niche.replace(" ", ""), "views": 0, "posts": 0, "trend": 1})
        return base
