"""CTA A/B testing — tracks which CTA types (save_bait, share_bait, comment_bait,
follow_bait, agree_disagree, fill_blank) drive the most engagement.

Uses the existing A/B results table in data_store to record and analyze
CTA performance by audience archetype.
"""
import sqlite3
import random
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

DB_PATH = Path(__file__).parent.parent.parent / "data" / "pipeline.db"

CTA_TYPES = ["save_bait", "share_bait", "comment_bait", "agree_disagree", "follow_bait", "fill_blank"]

# Default weights for CTA selection (research-backed, 2024-2026)
# Save bait has highest algorithmic value; share bait has highest reach value
DEFAULT_WEIGHTS = {
    "save_bait": 30,
    "share_bait": 25,
    "comment_bait": 20,
    "agree_disagree": 15,
    "follow_bait": 7,
    "fill_blank": 3,
}


def _get_connection():
    return sqlite3.connect(str(DB_PATH), timeout=5)


def record_cta_outcome(cta_type: str, audience: str, saved: int, comments: int,
                       reach: int, shares: int = 0) -> None:
    """Record the engagement outcome for a specific CTA type + audience."""
    conn = _get_connection()
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS cta_performance (
                cta_type TEXT NOT NULL,
                audience TEXT NOT NULL,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                saved INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                reach INTEGER DEFAULT 0
            )"""
        )
        conn.execute(
            "INSERT INTO cta_performance (cta_type, audience, saved, comments, shares, reach) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (cta_type, audience, saved, comments, shares, reach),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def get_cta_performance(audience: str = "", window_days: int = 60) -> dict:
    """Return avg engagement per CTA type, optionally filtered by audience.

    Returns {cta_type: {n, avg_saved, avg_comments, avg_shares, avg_reach, score}}
    """
    cutoff = (datetime.utcnow() - timedelta(days=window_days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_connection()
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS cta_performance (
                cta_type TEXT NOT NULL,
                audience TEXT NOT NULL,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                saved INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                reach INTEGER DEFAULT 0
            )"""
        )
        query = "SELECT cta_type, saved, comments, shares, reach FROM cta_performance WHERE posted_at >= ?"
        params = (cutoff,)
        if audience:
            query += " AND audience = ?"
            params = (cutoff, audience)

        rows = conn.execute(query, params).fetchall()

        cta_data = defaultdict(list)
        for row in rows:
            cta_type = row[0]
            reach = max(row[3] or 0, 1)
            # Engagement rate: (saved*3 + comments*2 + shares*2.5) / reach
            score = (row[1] * 3.0 + row[2] * 2.0 + row[3] * 2.5) / reach
            cta_data[cta_type].append({
                "saved": row[1] or 0, "comments": row[2] or 0,
                "shares": row[3] or 0, "reach": row[3] or 0,
                "score": score,
            })

        result = {}
        for cta_type, data in cta_data.items():
            n = len(data)
            if n == 0:
                continue
            result[cta_type] = {
                "n": n,
                "avg_saved": sum(d["saved"] for d in data) / n,
                "avg_comments": sum(d["comments"] for d in data) / n,
                "avg_shares": sum(d["shares"] for d in data) / n,
                "avg_reach": sum(d["reach"] for d in data) / n,
                "score": sum(d["score"] for d in data) / n,
            }

        return result
    except Exception:
        return {}
    finally:
        conn.close()


def recommend_cta_type(audience: str = "") -> str:
    """Recommend the best CTA type using Thompson Sampling over historical data.

    Falls back to weighted random from DEFAULT_WEIGHTS when insufficient data.
    """
    perf = get_cta_performance(audience=audience, window_days=60)

    # Thompson Sampling: sample from Beta(alpha, beta) for each CTA type
    best_sample = -1.0
    best_cta = None

    for cta_type in CTA_TYPES:
        data = perf.get(cta_type)
        if data and data["n"] >= 3:
            # Data-backed: use actual performance
            alpha = data["score"] * 100 + 1
            beta_param = max(1, 100 - data["score"] * 100 + 1)
            sample = random.betavariate(alpha, beta_param)
        else:
            # Prior: use default weight as prior
            prior = DEFAULT_WEIGHTS.get(cta_type, 10) / 100
            alpha = prior * 10 + 1
            beta_param = (1 - prior) * 10 + 1
            sample = random.betavariate(alpha, beta_param)

        if sample > best_sample:
            best_sample = sample
            best_cta = cta_type

    return best_cta or "save_bait"


def get_cta_report(audience: str = "") -> dict:
    """Full CTA performance report."""
    perf = get_cta_performance(audience=audience)

    ranked = sorted(perf.items(), key=lambda x: x[1]["score"], reverse=True)

    return {
        "top_performing": [
            {"cta_type": cta, "n": data["n"], "score": round(data["score"], 3),
             "avg_saved": round(data["avg_saved"], 1),
             "avg_comments": round(data["avg_comments"], 1)}
            for cta, data in ranked[:5]
        ],
        "recommended_next": recommend_cta_type(audience),
        "total_tracked": sum(d["n"] for d in perf.values()),
    }