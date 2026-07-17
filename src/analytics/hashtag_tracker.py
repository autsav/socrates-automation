"""Hashtag performance tracker — tracks which hashtags drive the most engagement.

Uses post_metrics data to correlate hashtags with reach/saves/comments.
Recommends the best hashtag mix for new posts.
"""
import sqlite3
import re
import json
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "pipeline.db"

# Hashtags banned for being overused (hurts reach per Instagram's 2024 algo)
BANNED_HASHTAGS = {
    # Generic spam magnets
    "#explore", "#explorepage", "#viral", "#fyp", "#foryou", "#foru",
    "#like4like", "#follow4follow", "#instagood", "#photooftheday",
    "#instadaily", "#picoftheday", "#best", "#amazing", "#awesome",
}

# Niche hashtags proven to work for philosophy/stoicism content
SEED_HASHTAGS = {
    "#stoicism": {"category": "niche", "est_reach": 0.8},
    "#philosophy": {"category": "broad", "est_reach": 0.6},
    "#socrates": {"category": "niche", "est_reach": 0.7},
    "#motivation": {"category": "broad", "est_reach": 0.5},
    "#mindset": {"category": "broad", "est_reach": 0.55},
    "#wisdom": {"category": "niche", "est_reach": 0.65},
    "#selfimprovement": {"category": "broad", "est_reach": 0.5},
    "#discipline": {"category": "niche", "est_reach": 0.7},
    "#mindfulness": {"category": "broad", "est_reach": 0.5},
    "#dailymotivation": {"category": "broad", "est_reach": 0.4},
}


def _get_connection():
    return sqlite3.connect(str(DB_PATH), timeout=5)


def _extract_hashtags(text: str) -> list[str]:
    """Extract #hashtags from a caption text."""
    if not text:
        return []
    return re.findall(r'#[\w]+', text.lower())


def get_hashtag_performance(window_days: int = 90) -> dict:
    """Return performance metrics per hashtag from historical data.

    Returns {hashtag: {n, avg_reach, avg_saved, avg_comments, avg_score}}.
    """
    from src.analytics.score_weights import engagement_score

    cutoff = (datetime.utcnow() - timedelta(days=window_days)).strftime("%Y-%m-%d")
    conn = _get_connection()
    try:
        rows = conn.execute(
            """SELECT p.quote_text, m.likes, m.comments, m.shares, m.saved, m.reach
               FROM posts p
               LEFT JOIN post_metrics m ON p.post_id = m.post_id
               WHERE p.posted_at >= ? AND p.dry_run = 0
               AND p.post_id IS NOT NULL""",
            (cutoff,)
        ).fetchall()

        hashtag_data = defaultdict(list)
        for row in rows:
            # Hashtags are embedded in the caption, but we store quote_text in posts
            # Try to get caption from the quote_text field (may contain hashtags)
            caption = row[0] or ""
            hashtags = _extract_hashtags(caption)
            metrics = {
                "likes": row[1] or 0, "comments": row[2] or 0,
                "shares": row[3] or 0, "saved": row[4] or 0, "reach": row[5] or 1,
            }
            score = engagement_score(metrics)
            for tag in hashtags:
                hashtag_data[tag].append({
                    "reach": metrics["reach"],
                    "saved": metrics["saved"],
                    "comments": metrics["comments"],
                    "score": score,
                })

        result = {}
        for tag, data in hashtag_data.items():
            n = len(data)
            if n == 0:
                continue
            result[tag] = {
                "n": n,
                "avg_reach": sum(d["reach"] for d in data) / n,
                "avg_saved": sum(d["saved"] for d in data) / n,
                "avg_comments": sum(d["comments"] for d in data) / n,
                "avg_score": sum(d["score"] for d in data) / n,
            }

        return result
    except Exception:
        return {}
    finally:
        conn.close()


def recommend_hashtags(audience: str = "", mood: str = "", n: int = 5) -> list[str]:
    """Recommend the best hashtag mix for a new post.

    Combines historical performance data with seed hashtags.
    Always returns 3-5 hashtags (Instagram 2024 algo rewards fewer, relevant tags).
    Banned hashtags are filtered out.
    """
    perf = get_hashtag_performance()

    # Start with performance-ranked hashtags that have data
    ranked = sorted(
        [(tag, data["avg_score"]) for tag, data in perf.items()
         if tag not in BANNED_HASHTAGS and data["n"] >= 2],
        key=lambda x: x[1],
        reverse=True
    )

    recommended = [tag for tag, _ in ranked[:n]]

    # Fill with seed hashtags if we don't have enough data-backed ones
    if len(recommended) < 3:
        # Audience-specific hashtags
        audience_tags = {
            "procrastinator": ["#discipline", "#motivation", "#stoicism"],
            "doomscroller": ["#mindfulness", "#stoicism", "#wisdom"],
            "stuck": ["#selfimprovement", "#philosophy", "#mindset"],
            "lazy": ["#discipline", "#motivation", "#stoicism"],
            "quitter": ["#motivation", "#stoicism", "#wisdom"],
            "lost": ["#philosophy", "#selfimprovement", "#mindset"],
            "overwhelmed": ["#mindfulness", "#stoicism", "#wisdom"],
        }
        base = audience_tags.get(audience, ["#stoicism", "#philosophy", "#socrates"])
        for tag in base:
            if tag not in recommended and tag not in BANNED_HASHTAGS:
                recommended.append(tag)
            if len(recommended) >= n:
                break

    return recommended[:n]


def is_banned(hashtag: str) -> bool:
    """Check if a hashtag is banned/overused."""
    return hashtag.lower() in BANNED_HASHTAGS


def get_hashtag_report() -> dict:
    """Full report: top performing, banned, and recommended hashtags."""
    perf = get_hashtag_performance()

    top = sorted(perf.items(), key=lambda x: x[1]["avg_score"], reverse=True)[:10]

    return {
        "top_performing": [
            {"hashtag": tag, "n": data["n"], "avg_score": round(data["avg_score"], 3),
             "avg_reach": round(data["avg_reach"], 1)}
            for tag, data in top
        ],
        "banned": list(BANNED_HASHTAGS),
        "recommended_mix": recommend_hashtags(),
        "total_tracked": len(perf),
    }