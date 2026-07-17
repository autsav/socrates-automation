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
        "template": "You already know what you need to do. So why haven't you?",
        "est_hold": 0.78,
    },
    "pattern_interrupt_2": {
        "category": "pattern_interrupt",
        "template": "Stop. You're about to scroll past something you needed today.",
        "est_hold": 0.80,
    },
    "question_1": {
        "category": "question",
        "template": "What if the life you're avoiding IS the one worth living?",
        "est_hold": 0.76,
    },
    "question_2": {
        "category": "question",
        "template": "What if you're not stuck — just too comfortable to move?",
        "est_hold": 0.79,
    },
    "confrontation_1": {
        "category": "confrontation",
        "template": "You're not busy. You're just avoiding what matters.",
        "est_hold": 0.82,
    },
    "confrontation_2": {
        "category": "confrontation",
        "template": "Socrates would call your daily routine a slow death.",
        "est_hold": 0.85,
    },
    "confrontation_3": {
        "category": "confrontation",
        "template": "The algorithm knows you're wasting your life. So do you.",
        "est_hold": 0.84,
    },
    "confrontation_4": {
        "category": "confrontation",
        "template": "You don't need motivation. You need a reality check.",
        "est_hold": 0.83,
    },
    "story_1": {
        "category": "story",
        "template": "2,400 years ago, a man was sentenced to death for asking questions you're too scared to ask.",
        "est_hold": 0.75,
    },
    "statistic_1": {
        "category": "statistic",
        "template": "90% of people will scroll past this. The 10% who stay are the ones who change.",
        "est_hold": 0.77,
    },
    "personalization_1": {
        "category": "personalization",
        "template": "You opened this for a reason. Let's find out which one.",
        "est_hold": 0.81,
    },
    "roast_1": {
        "category": "roast",
        "template": "Socrates roasted people for free 2,400 years ago. You pay for therapy.",
        "est_hold": 0.83,
    },
    "roast_2": {
        "category": "roast",
        "template": "Your screen time report would make Socrates weep.",
        "est_hold": 0.86,
    },
    "verdict_1": {
        "category": "verdict",
        "template": "Socrates would have thoughts on what you're doing right now.",
        "est_hold": 0.80,
    },
    "debate_1": {
        "category": "debate",
        "template": "Hot take: comfort is the new prison. And you built the walls.",
        "est_hold": 0.84,
    },
    "quote_first_1": {
        "category": "quote_first",
        "template": '"{quote_truncated}" — and you thought YOUR life was hard.',
        "est_hold": 0.72,
    },
}


def _get_connection():
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def get_hook_performance(hook_id: str, window_days: int = 30) -> dict:
    """Return avg metrics for a specific hook template.
    Gracefully returns zeroed dict if hook_id column doesn't exist in posts table."""
    cutoff = (datetime.utcnow() - timedelta(days=window_days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        # Check if hook_id column exists in posts table
        cursor.execute("PRAGMA table_info(posts)")
        columns = {row[1] for row in cursor.fetchall()}
        if "hook_id" not in columns:
            return {
                "hook_id": hook_id,
                "n": 0,
                "avg_saved": 0.0,
                "avg_comments": 0.0,
                "avg_reach": 0.0,
                "avg_likes": 0.0,
                "composite_score": 0.0,
            }
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
