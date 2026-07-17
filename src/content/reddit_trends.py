"""Reddit trend source — fetches trending topics from philosophy/motivation subreddits.

Adds Reddit as a trend source alongside GNews and Google Trends.
Uses Reddit's public JSON API (no auth needed, just needs a custom User-Agent).
Gracefully degrades to [] on any error.
"""
import re
import time

import requests

REDDIT_API = "https://www.reddit.com"

# Subreddits where philosophy/stoicism/motivation topics trend
_TARGET_SUBS = [
    "philosophy",
    "Stoicism",
    "getmotivated",
    "selfimprovement",
    "Productivity",
    "discipline",
]

# Minimum upvotes to be considered "trending"
_MIN_UPVOTES = 50

# Cache to avoid hammering Reddit (5-minute TTL)
_CACHE: dict = {}
_CACHE_TTL = 300  # seconds


def _is_safe_topic(text: str) -> bool:
    """Filter out topics that are unsafe for a stoic-philosophy brand."""
    from src.content.trend_sources import is_unsafe
    return not is_unsafe(text)


def reddit_trending(limit: int = 15) -> list[dict]:
    """Fetch trending topics from target subreddits.

    Returns [{topic, source, score}] where score is the Reddit upvote count.
    Uses a 5-minute cache to avoid rate limiting.
    """
    cache_key = f"reddit_trending_{limit}"
    now = time.time()

    if cache_key in _CACHE:
        cached_at, cached_data = _CACHE[cache_key]
        if now - cached_at < _CACHE_TTL:
            return cached_data

    results = []
    seen = set()

    for sub in _TARGET_SUBS:
        try:
            url = f"{REDDIT_API}/r/{sub}/hot.json?limit=10"
            headers = {"User-Agent": "SocratesBot/1.0 (philosophy content research)"}
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            posts = resp.json().get("data", {}).get("children", [])

            for post in posts:
                pd = post.get("data", {})
                title = pd.get("title", "").strip()
                ups = pd.get("ups", 0)
                stickied = pd.get("stickied", False)

                if not title or stickied or ups < _MIN_UPVOTES:
                    continue

                key = title.lower()[:80]
                if key in seen:
                    continue
                if not _is_safe_topic(title):
                    continue

                seen.add(key)
                results.append({
                    "topic": title,
                    "source": f"reddit/r/{sub}",
                    "score": ups,
                })
        except Exception:
            continue

    # Sort by upvotes (highest first)
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    results = results[:limit]

    _CACHE[cache_key] = (now, results)
    return results


def reddit_trending_for_socrates(limit: int = 15) -> list[dict]:
    """Alias matching the interface expected by fetch_trends."""
    topics = reddit_trending(limit)
    # Strip score for compatibility with fetch_trends format
    return [{"topic": t["topic"], "source": t["source"]} for t in topics]