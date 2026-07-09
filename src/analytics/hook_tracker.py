"""
Hook Variant Tracker

Tracks which hook templates perform best by correlating hook_id with metrics.
Provides Thompson Sampling for hook selection + statistical reporting.
"""

import sqlite3
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import Callable

DB_PATH = Path(__file__).parent.parent.parent / "data" / "pipeline.db"

# ── Hook Template Registry ───────────────────────────────────────────────────
# Each hook has: id, category, text template, estimated_3s_hold_rate

HOOK_TEMPLATES = {
    "pattern_interrupt_1": {
        "category": "pattern_interrupt",
        "template": "You already know what you need to do.",
        "est_hold": 0.72,
    },
    "pattern_interrupt_2": {
        "category": "pattern_interrupt",
        "template": "Stop waiting to feel ready.",
        "est_hold": 0.68,
    },
    "question_1": {
        "category": "question",
        "template": "What if waiting IS the mistake?",
        "est_hold": 0.70,
    },
    "question_2": {
        "category": "question",
        "template": "What if you're not stuck — just afraid?",
        "est_hold": 0.74,
    },
    "confrontation_1": {
        "category": "confrontation",
        "template": "You've delayed this long enough.",
        "est_hold": 0.65,
    },
    "confrontation_2": {
        "category": "confrontation",
        "template": "The algorithm is not on your side.",
        "est_hold": 0.69,
    },
    "story_1": {
        "category": "story",
        "template": "Meet Alex. Alex scrolls 4 hours a day. Today Alex found Socrates.",
        "est_hold": 0.62,
    },
    "statistic_1": {
        "category": "statistic",
        "template": "90% of people skip this. Don't be one of them.",
        "est_hold": 0.71,
    },
    "personalization_1": {
        "category": "personalization",
        "template": "Hey {audience} — this is specifically for you.",
        "est_hold": 0.75,
    },
    "quote_first_1": {
        "category": "quote_first",
        "template": "\"{quote_truncated}\"",
        "est_hold": 0.58,
    },
}


def _get_connection():
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def get_hook_performance(hook_id: str, window_days: int = 30) -> dict:
    """Return avg metrics for a specific hook template."""
    cutoff = (datetime.utcnow() - timedelta(days=window_days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) as n,
                   AVG(COALESCE(m.saved, 0)) as avg_saved,
                   AVG(COALESCE(m.comments, 0)) as avg_comments,
                   AVG(COALESCE(m.reach, 0)) as avg_reach,
                   AVG(COALESCE(m.likes, 0)) as avg_likes
            FROM posts p
            LEFT JOIN post_metrics m ON p.post_id = m.post_id
            WHERE p.hook_id = ? AND p.posted_at >= ?
            """,
            (hook_id, cutoff),
        )
        row = cursor.fetchone()
        n, avg_saved, avg_comments, avg_reach, avg_likes = row
        return {
            "hook_id": hook_id,
            "n": n or 0,
            "avg_saved": round(avg_saved or 0, 1),
            "avg_comments": round(avg_comments or 0, 1),
            "avg_reach": round(avg_reach or 0, 1),
            "avg_likes": round(avg_likes or 0, 1),
            "composite_score": round(
                (avg_saved or 0) * 3.0 + (avg_comments or 0) * 2.0 + (avg_reach or 0) * 0.0015,
                1,
            ) if n > 0 else 0.0,
        }
    finally:
        conn.close()


def get_all_hook_rankings(window_days: int = 30) -> list[dict]:
    """Return all hooks ranked by composite performance score."""
    rankings = []
    for hook_id in HOOK_TEMPLATES:
        perf = get_hook_performance(hook_id, window_days)
        perf.update(HOOK_TEMPLATES[hook_id])
        rankings.append(perf)
    rankings.sort(key=lambda x: x["composite_score"], reverse=True)
    return rankings


def pick_best_hook(
    audience: str,
    quote_text: str,
    method: str = "thompson",
    exploration_rate: float = 0.15,
) -> dict:
    """
    Select the best hook template using Thompson Sampling or epsilon-greedy.
    Returns dict with hook_id, rendered_text, category, confidence.
    """
    hook_ids = list(HOOK_TEMPLATES.keys())

    if method == "random":
        chosen = random.choice(hook_ids)
        return _render_hook(chosen, audience, quote_text)

    if method == "epsilon_greedy":
        if random.random() < exploration_rate:
            chosen = random.choice(hook_ids)
            return _render_hook(chosen, audience, quote_text)
        rankings = get_all_hook_rankings(window_days=30)
        if not rankings or rankings[0]["n"] == 0:
            chosen = random.choice(hook_ids)
            return _render_hook(chosen, audience, quote_text)
        chosen = rankings[0]["hook_id"]
        return _render_hook(chosen, audience, quote_text)

    # Default: Thompson Sampling
    best_sample = -1.0
    best_hook = None
    for hook_id in hook_ids:
        perf = get_hook_performance(hook_id, window_days=30)
        n = perf["n"]
        composite = perf["composite_score"]
        # Beta prior: prior_mean = estimated hold from template registry
        prior_mean = HOOK_TEMPLATES[hook_id]["est_hold"] * 100
        alpha = composite + prior_mean * 0.5 + 1
        beta_param = max(1, n - composite + prior_mean * 0.5 + 1)
        sample = random.betavariate(alpha, beta_param)
        if sample > best_sample:
            best_sample = sample
            best_hook = hook_id

    if best_hook is None:
        best_hook = random.choice(hook_ids)

    return _render_hook(best_hook, audience, quote_text)


def _render_hook(hook_id: str, audience: str, quote_text: str) -> dict:
    template = HOOK_TEMPLATES[hook_id]["template"]
    text = template.replace("{audience}", audience)
    # Truncate quote for quote-first hooks
    truncated = quote_text[:40] + "..." if len(quote_text) > 40 else quote_text
    text = text.replace("{quote_truncated}", f'"{truncated}"')
    return {
        "hook_id": hook_id,
        "hook_text": text,
        "category": HOOK_TEMPLATES[hook_id]["category"],
        "template": template,
    }


def record_hook_outcome(
    hook_id: str,
    actual_saved: int,
    actual_comments: int,
    actual_reach: int,
) -> None:
    """
    Update hook performance table. This is a separate table from posts
    for fast hook-specific queries.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS hook_performance (
                hook_id TEXT NOT NULL,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                saved INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                reach INTEGER DEFAULT 0
            )
            """
        )
        cursor.execute(
            "INSERT INTO hook_performance (hook_id, saved, comments, reach) VALUES (?, ?, ?, ?)",
            (hook_id, actual_saved, actual_comments, actual_reach),
        )
        conn.commit()
    finally:
        conn.close()


def get_hook_leaderboard(window_days: int = 30, min_trials: int = 3) -> dict:
    """
    Return a leaderboard dict with top 3 hooks and category winners.
    """
    rankings = get_all_hook_rankings(window_days)
    qualified = [r for r in rankings if r["n"] >= min_trials]
    unqualified = [r for r in rankings if r["n"] < min_trials]

    # Category winners
    categories = {}
    for r in qualified:
        cat = r["category"]
        if cat not in categories or r["composite_score"] > categories[cat]["composite_score"]:
            categories[cat] = r

    return {
        "top_overall": qualified[:3] if qualified else unqualified[:3],
        "category_winners": categories,
        "needs_more_data": [r["hook_id"] for r in unqualified],
        "window_days": window_days,
        "total_trials": sum(r["n"] for r in rankings),
    }
