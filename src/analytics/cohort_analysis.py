"""
Cohort Analysis + Funnel Tracking

Tracks performance by time cohorts and full conversion funnel:
Impression → View → 3s Hold → Completion → Like → Comment → Save → Follow → DM

Designed to identify drop-off points and optimize the weakest link.
"""

import sqlite3
import math
from pathlib import Path
from datetime import datetime, timedelta
from typing import Callable

DB_PATH = Path(__file__).parent.parent.parent / "data" / "pipeline.db"


def _get_connection():
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ── Cohort Analysis ────────────────────────────────────────────────────────────

def get_cohort_performance(
    dimension: str,
    value: str,
    window_days: int = 90,
) -> dict:
    """
    Get aggregate performance for a specific cohort.
    dimension: 'posting_slot', 'mood', 'audience', 'day_of_week'
    """
    cutoff = (datetime.utcnow() - timedelta(days=window_days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_connection()
    try:
        cursor = conn.cursor()

        if dimension == "day_of_week":
            # SQLite strftime %w: 0=Sun, 1=Mon...
            cursor.execute(
                """
                SELECT COUNT(*) as n,
                       AVG(COALESCE(m.reach, 0)) as avg_reach,
                       AVG(COALESCE(m.saved, 0)) as avg_saved,
                       AVG(COALESCE(m.comments, 0)) as avg_comments,
                       AVG(COALESCE(m.likes, 0)) as avg_likes,
                       AVG(COALESCE(m.shares, 0)) as avg_shares,
                       AVG(COALESCE(m.impressions, 0)) as avg_impressions
                FROM posts p
                LEFT JOIN post_metrics m ON p.post_id = m.post_id
                WHERE p.posted_at >= ? AND CAST(strftime('%w', p.posted_at) AS INTEGER) = ?
                  AND m.post_id IS NOT NULL
                """,
                (cutoff, int(value)),
            )
        else:
            cursor.execute(
                f"""
                SELECT COUNT(*) as n,
                       AVG(COALESCE(m.reach, 0)) as avg_reach,
                       AVG(COALESCE(m.saved, 0)) as avg_saved,
                       AVG(COALESCE(m.comments, 0)) as avg_comments,
                       AVG(COALESCE(m.likes, 0)) as avg_likes,
                       AVG(COALESCE(m.shares, 0)) as avg_shares,
                       AVG(COALESCE(m.impressions, 0)) as avg_impressions
                FROM posts p
                LEFT JOIN post_metrics m ON p.post_id = m.post_id
                WHERE p.posted_at >= ? AND p.{dimension} = ? AND m.post_id IS NOT NULL
                """,
                (cutoff, value),
            )

        row = cursor.fetchone()
        n, avg_reach, avg_saved, avg_comments, avg_likes, avg_shares, avg_impressions = row

        if not n:
            return {"dimension": dimension, "value": value, "n": 0, "status": "no_data"}

        return {
            "dimension": dimension,
            "value": value,
            "n": n,
            "avg_reach": round(avg_reach or 0, 1),
            "avg_saved": round(avg_saved or 0, 1),
            "avg_comments": round(avg_comments or 0, 1),
            "avg_likes": round(avg_likes or 0, 1),
            "avg_shares": round(avg_shares or 0, 1),
            "avg_impressions": round(avg_impressions or 0, 1),
            "save_rate": round((avg_saved or 0) / max(avg_reach or 0, 1) * 100, 2),
            "engagement_rate": round((avg_likes + avg_comments + avg_saved) / max(avg_reach or 0, 1) * 100, 2),
        }
    finally:
        conn.close()


def compare_cohorts(dimension: str, values: list[str], window_days: int = 90) -> list[dict]:
    """Compare multiple cohorts side-by-side, sorted by engagement rate."""
    results = []
    for value in values:
        result = get_cohort_performance(dimension, value, window_days)
        if result.get("n", 0) > 0:
            results.append(result)
    results.sort(key=lambda x: x.get("engagement_rate", 0), reverse=True)
    return results


def get_optimal_posting_window(window_days: int = 90) -> dict:
    """Find the best posting slot based on historical data."""
    slots = [0, 1, 2]
    results = compare_cohorts("posting_slot", [str(s) for s in slots], window_days)
    if not results:
        return {"status": "insufficient_data", "recommended_slot": 2, "confidence": "low"}

    best = results[0]
    slot_map = {0: "morning", 1: "midday", 2: "evening"}
    return {
        "status": "ok",
        "recommended_slot": int(best["value"]),
        "slot_name": slot_map.get(int(best["value"]), best["value"]),
        "avg_engagement_rate": best["engagement_rate"],
        "avg_reach": best["avg_reach"],
        "n_posts": best["n"],
        "all_slots": results,
        "confidence": "high" if best["n"] >= 10 else "medium" if best["n"] >= 5 else "low",
    }


def get_day_of_week_breakdown(window_days: int = 90) -> list[dict]:
    """Performance by day of week (0=Sunday, 6=Saturday)."""
    days = list(range(7))
    results = compare_cohorts("day_of_week", [str(d) for d in days], window_days)
    day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    for r in results:
        r["day_name"] = day_names[int(r["value"])]
    return results


# ── Funnel Tracking ────────────────────────────────────────────────────────────

FUNNEL_STAGES = [
    "impressions",
    "reach",
    "views",
    "hold_3s",
    "completions",
    "likes",
    "comments",
    "saves",
    "shares",
    "follows",
    "dms",
]


def record_funnel(post_id: str, stage: str, count: int) -> None:
    """Record a funnel stage metric for a post."""
    if stage not in FUNNEL_STAGES:
        raise ValueError(f"Unknown funnel stage: {stage}. Must be one of {FUNNEL_STAGES}")

    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS funnel_metrics (
                post_id TEXT PRIMARY KEY,
                impressions INTEGER DEFAULT 0,
                reach INTEGER DEFAULT 0,
                views INTEGER DEFAULT 0,
                hold_3s INTEGER DEFAULT 0,
                completions INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                saves INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                follows INTEGER DEFAULT 0,
                dms INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            f"""
            INSERT INTO funnel_metrics (post_id, {stage}, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(post_id) DO UPDATE SET
                {stage} = excluded.{stage},
                updated_at = CURRENT_TIMESTAMP
            """,
            (post_id, count),
        )
        conn.commit()
    finally:
        conn.close()


def get_funnel(post_id: str) -> dict | None:
    """Get full funnel for a specific post."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM funnel_metrics WHERE post_id = ?",
            (post_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))
    finally:
        conn.close()


def compute_funnel_rates(post_id: str) -> dict:
    """Compute conversion rates between funnel stages."""
    funnel = get_funnel(post_id)
    if funnel is None:
        return {"status": "no_data", "post_id": post_id}

    impressions = max(funnel.get("impressions", 0), 1)
    reach = max(funnel.get("reach", 0), 1)
    views = max(funnel.get("views", 0), 1)
    hold_3s = max(funnel.get("hold_3s", 0), 1)
    completions = max(funnel.get("completions", 0), 1)

    return {
        "post_id": post_id,
        "impression_to_reach": round(funnel.get("reach", 0) / impressions * 100, 2),
        "reach_to_view": round(funnel.get("views", 0) / reach * 100, 2),
        "view_to_hold": round(funnel.get("hold_3s", 0) / views * 100, 2),
        "hold_to_completion": round(funnel.get("completions", 0) / hold_3s * 100, 2),
        "completion_to_like": round(funnel.get("likes", 0) / completions * 100, 2),
        "completion_to_save": round(funnel.get("saves", 0) / completions * 100, 2),
        "completion_to_comment": round(funnel.get("comments", 0) / completions * 100, 2),
        "completion_to_share": round(funnel.get("shares", 0) / completions * 100, 2),
        "completion_to_follow": round(funnel.get("follows", 0) / completions * 100, 2),
        "completion_to_dm": round(funnel.get("dms", 0) / completions * 100, 2),
        "bottleneck": _find_bottleneck(funnel),
    }


def _find_bottleneck(funnel: dict) -> str:
    """Identify the biggest drop-off in the funnel."""
    stages = [
        ("impression_to_reach", funnel.get("reach", 0) / max(funnel.get("impressions", 0), 1)),
        ("reach_to_view", funnel.get("views", 0) / max(funnel.get("reach", 0), 1)),
        ("view_to_hold", funnel.get("hold_3s", 0) / max(funnel.get("views", 0), 1)),
        ("hold_to_completion", funnel.get("completions", 0) / max(funnel.get("hold_3s", 0), 1)),
        ("completion_to_save", funnel.get("saves", 0) / max(funnel.get("completions", 0), 1)),
    ]
    # Find the lowest conversion rate
    bottleneck, rate = min(stages, key=lambda x: x[1])
    return f"{bottleneck} ({rate*100:.1f}%)"


def aggregate_funnel_averages(window_days: int = 30) -> dict:
    """Average funnel metrics across all posts in window."""
    cutoff = (datetime.utcnow() - timedelta(days=window_days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT AVG(impressions) as avg_impressions,
                   AVG(reach) as avg_reach,
                   AVG(views) as avg_views,
                   AVG(hold_3s) as avg_hold_3s,
                   AVG(completions) as avg_completions,
                   AVG(likes) as avg_likes,
                   AVG(comments) as avg_comments,
                   AVG(saves) as avg_saves,
                   AVG(shares) as avg_shares,
                   AVG(follows) as avg_follows,
                   AVG(dms) as avg_dms
            FROM funnel_metrics f
            JOIN posts p ON f.post_id = p.post_id
            WHERE p.posted_at >= ?
            """,
            (cutoff,),
        )
        row = cursor.fetchone()
        if row is None or row[0] is None:
            return {"status": "insufficient_data", "n": 0}

        keys = [
            "avg_impressions", "avg_reach", "avg_views", "avg_hold_3s",
            "avg_completions", "avg_likes", "avg_comments", "avg_saves",
            "avg_shares", "avg_follows", "avg_dms",
        ]
        return dict(zip(keys, [round(v or 0, 1) for v in row]))
    finally:
        conn.close()


def get_top_performing_posts(n: int = 5, window_days: int = 30) -> list[dict]:
    """Return top N posts by composite engagement score."""
    cutoff = (datetime.utcnow() - timedelta(days=window_days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.id, p.quote_text, p.audience, p.mood, p.posted_at,
                   (m.saved * 3.0 + m.comments * 2.0 + m.reach * 0.0015 + m.shares * 2.5) as score,
                   m.saved, m.comments, m.reach, m.likes, m.shares
            FROM posts p
            JOIN post_metrics m ON p.post_id = m.post_id
            WHERE p.posted_at >= ? AND m.post_id IS NOT NULL
            ORDER BY score DESC
            LIMIT ?
            """,
            (cutoff, n),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": r[0],
                "quote_text": r[1][:60] + "..." if len(r[1]) > 60 else r[1],
                "audience": r[2],
                "mood": r[3],
                "posted_at": r[4],
                "composite_score": round(r[5], 1),
                "saved": r[6],
                "comments": r[7],
                "reach": r[8],
                "likes": r[9],
                "shares": r[10],
            }
            for r in rows
        ]
    finally:
        conn.close()


def get_bottom_performing_posts(n: int = 3, window_days: int = 30) -> list[dict]:
    """Return bottom N posts by composite score (for learning)."""
    cutoff = (datetime.utcnow() - timedelta(days=window_days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.id, p.quote_text, p.audience, p.mood, p.posted_at,
                   (m.saved * 3.0 + m.comments * 2.0 + m.reach * 0.0015 + m.shares * 2.5) as score,
                   m.saved, m.comments, m.reach, m.likes, m.shares
            FROM posts p
            JOIN post_metrics m ON p.post_id = m.post_id
            WHERE p.posted_at >= ? AND m.post_id IS NOT NULL
            ORDER BY score ASC
            LIMIT ?
            """,
            (cutoff, n),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": r[0],
                "quote_text": r[1][:60] + "..." if len(r[1]) > 60 else r[1],
                "audience": r[2],
                "mood": r[3],
                "posted_at": r[4],
                "composite_score": round(r[5], 1),
                "saved": r[6],
                "comments": r[7],
                "reach": r[8],
                "likes": r[9],
                "shares": r[10],
            }
            for r in rows
        ]
    finally:
        conn.close()


def statistical_significance(
    dimension: str,
    value_a: str,
    value_b: str,
    window_days: int = 90,
) -> dict:
    """
    Test if two cohorts differ significantly using Welch's t-test.
    Returns effect size and p-value estimate.
    """
    cutoff = (datetime.utcnow() - timedelta(days=window_days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT (m.saved * 3.0 + m.comments * 2.0 + m.reach * 0.0015 + m.shares * 2.5)
            FROM posts p JOIN post_metrics m ON p.post_id = m.post_id
            WHERE p.posted_at >= ? AND p.{dimension} = ? AND m.post_id IS NOT NULL
            """,
            (cutoff, value_a),
        )
        a_vals = [r[0] for r in cursor.fetchall()]

        cursor.execute(
            f"""
            SELECT (m.saved * 3.0 + m.comments * 2.0 + m.reach * 0.0015 + m.shares * 2.5)
            FROM posts p JOIN post_metrics m ON p.post_id = m.post_id
            WHERE p.posted_at >= ? AND p.{dimension} = ? AND m.post_id IS NOT NULL
            """,
            (cutoff, value_b),
        )
        b_vals = [r[0] for r in cursor.fetchall()]
    finally:
        conn.close()

    if len(a_vals) < 3 or len(b_vals) < 3:
        return {
            "status": "insufficient_data",
            "n_a": len(a_vals),
            "n_b": len(b_vals),
            "message": "Need ≥3 samples per group",
        }

    mean_a = sum(a_vals) / len(a_vals)
    mean_b = sum(b_vals) / len(b_vals)
    var_a = sum((x - mean_a) ** 2 for x in a_vals) / (len(a_vals) - 1) if len(a_vals) > 1 else 0
    var_b = sum((x - mean_b) ** 2 for x in b_vals) / (len(b_vals) - 1) if len(b_vals) > 1 else 0

    # Welch's t-statistic
    se = math.sqrt(var_a / len(a_vals) + var_b / len(b_vals))
    t_stat = (mean_a - mean_b) / se if se > 0 else 0

    # Cohen's d (effect size)
    pooled_std = math.sqrt((var_a + var_b) / 2)
    cohens_d = (mean_a - mean_b) / pooled_std if pooled_std > 0 else 0

    return {
        "status": "ok",
        "dimension": dimension,
        "value_a": value_a,
        "value_b": value_b,
        "mean_a": round(mean_a, 2),
        "mean_b": round(mean_b, 2),
        "n_a": len(a_vals),
        "n_b": len(b_vals),
        "t_statistic": round(t_stat, 3),
        "cohens_d": round(cohens_d, 3),
        "effect_size": "large" if abs(cohens_d) >= 0.8 else "medium" if abs(cohens_d) >= 0.5 else "small",
    }
