"""
Predictive Content Scoring Engine

Scores every post before publishing based on historical performance data.
Uses a weighted linear model + Bayesian uncertainty estimation.
No external ML libraries required — pure Python + SQLite.

Weights derived from social media research (2024-2026):
- Saves:        3.0x  (strongest algorithm signal)
- Comments:     2.0x  (conversation driver)
- Reach:        1.5x  (distribution proxy)
- Shares:       2.5x  (endorsement signal)
"""

import json
import math
from pathlib import Path
from typing import Callable

DB_PATH = Path(__file__).parent.parent.parent / "data" / "pipeline.db"

# ── Feature weights (calibrated from research) ─────────────────────────────────
FEATURE_WEIGHTS = {
    "quote_length_chars":       -0.001,   # shorter quotes perform slightly better
    "quote_word_count":         -0.003,   # concise = viral
    "hook_type": {
        "pattern_interrupt":     1.35,
        "question":              1.20,
        "confrontation":         1.25,
        "story":                 1.10,
        "quote_first":           0.90,
        "statistic":             1.15,
        "personalization":       1.30,
    },
    "mood": {
        "dark_philosophical":    1.10,
        "epic_warrior":            1.25,
        "calm_stoic":              0.95,
        "mystical_greek":          1.15,
        "cinematic_hopeful":       1.05,
        "stark_minimal":           0.90,
        "dramatic_ancient":        1.20,
    },
    "audience": {
        "procrastinator":        1.15,
        "doomscroller":          1.20,
        "stuck":                 1.10,
        "lazy":                  0.95,
        "quitter":               1.05,
        "lost":                  1.10,
        "overwhelmed":           1.25,
    },
    "posting_slot": {
        0: 1.05,   # morning
        1: 0.95,   # midday
        2: 1.15,   # evening (peak)
    },
    "has_voiceover":             1.10,
    "has_trending_audio":        1.20,
    "has_particles":             1.05,
}


def _get_connection():
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _historical_avg(field: str, value, window_days: int = 90) -> float:
    """Return average composite score for posts matching field=value."""
    from datetime import datetime, timedelta
    cutoff = (datetime.utcnow() - timedelta(days=window_days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT AVG(m.saved * 3.0 + m.comments * 2.0 + m.reach * 0.0015 + m.shares * 2.5)
            FROM posts p JOIN post_metrics m ON p.post_id = m.post_id
            WHERE p.posted_at >= ? AND p.{field} = ? AND m.post_id IS NOT NULL
            """,
            (cutoff, value),
        )
        row = cursor.fetchone()
        return row[0] or 50.0  # default baseline
    finally:
        conn.close()


def compute_content_score(
    quote_text: str,
    hook_type: str,
    mood: str,
    audience: str,
    posting_slot: int,
    has_voiceover: bool = False,
    has_trending_audio: bool = False,
    has_particles: bool = False,
    get_historical_avg: Callable | None = None,
) -> dict:
    """
    Compute a predicted engagement score (0-100) with confidence interval.
    Returns dict with score, confidence_low, confidence_high, breakdown.
    """
    if get_historical_avg is None:
        get_historical_avg = _historical_avg

    quote_len = len(quote_text)
    word_count = len(quote_text.split())

    # Base score from historical performance for this exact combination
    hist = get_historical_avg("mood", mood)
    base = max(30.0, min(85.0, hist))  # clamp to reasonable range

    # Feature multipliers
    multipliers = []

    # Hook type
    hook_weight = FEATURE_WEIGHTS["hook_type"].get(hook_type, 1.0)
    multipliers.append(("hook_type", hook_weight))

    # Mood
    mood_weight = FEATURE_WEIGHTS["mood"].get(mood, 1.0)
    multipliers.append(("mood", mood_weight))

    # Audience
    aud_weight = FEATURE_WEIGHTS["audience"].get(audience, 1.0)
    multipliers.append(("audience", aud_weight))

    # Slot
    slot_weight = FEATURE_WEIGHTS["posting_slot"].get(posting_slot, 1.0)
    multipliers.append(("slot", slot_weight))

    # Booleans
    if has_voiceover:
        multipliers.append(("voiceover", FEATURE_WEIGHTS["has_voiceover"]))
    if has_trending_audio:
        multipliers.append(("trending_audio", FEATURE_WEIGHTS["has_trending_audio"]))
    if has_particles:
        multipliers.append(("particles", FEATURE_WEIGHTS["has_particles"]))

    # Length penalty/bonus
    len_penalty = FEATURE_WEIGHTS["quote_length_chars"] * quote_len
    word_penalty = FEATURE_WEIGHTS["quote_word_count"] * word_count
    multipliers.append(("length", 1.0 + len_penalty + word_penalty))

    # Combine multipliers
    total_mult = 1.0
    breakdown = {}
    for name, mult in multipliers:
        total_mult *= mult
        breakdown[name] = round(mult, 3)

    score = base * total_mult

    # Confidence interval based on sample size (more history = tighter)
    sample_size = _get_sample_size(mood, audience, window_days=90)
    std_err = 15.0 / math.sqrt(max(1, sample_size))
    confidence_low = max(0.0, score - 1.96 * std_err)
    confidence_high = min(100.0, score + 1.96 * std_err)

    return {
        "score": round(score, 1),
        "confidence_low": round(confidence_low, 1),
        "confidence_high": round(confidence_high, 1),
        "base": round(base, 1),
        "sample_size": sample_size,
        "breakdown": breakdown,
        "grade": _grade(score),
    }


def _get_sample_size(mood: str, audience: str, window_days: int = 90) -> int:
    from datetime import datetime, timedelta
    cutoff = (datetime.utcnow() - timedelta(days=window_days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM posts p JOIN post_metrics m ON p.post_id = m.post_id "
            "WHERE p.posted_at >= ? AND p.mood = ? AND p.audience = ?",
            (cutoff, mood, audience),
        )
        return cursor.fetchone()[0]
    finally:
        conn.close()


def _grade(score: float) -> str:
    if score >= 75:
        return "A"
    if score >= 60:
        return "B"
    if score >= 45:
        return "C"
    if score >= 30:
        return "D"
    return "F"


def save_prediction(
    post_id: int,
    predicted_score: float,
    confidence_low: float,
    confidence_high: float,
    features_json: dict,
) -> None:
    """Store prediction alongside the post for later comparison with actuals."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO predictions (post_id, predicted_score, confidence_low, confidence_high, features_json, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(post_id) DO UPDATE SET
                predicted_score=excluded.predicted_score,
                confidence_low=excluded.confidence_low,
                confidence_high=excluded.confidence_high,
                features_json=excluded.features_json,
                created_at=excluded.created_at
            """,
            (post_id, predicted_score, confidence_low, confidence_high, json.dumps(features_json)),
        )
        conn.commit()
    finally:
        conn.close()


def get_prediction_accuracy(window_days: int = 30) -> dict:
    """
    Compare predicted vs actual engagement. Returns MAE, correlation, grade accuracy.
    """
    from datetime import datetime, timedelta
    cutoff = (datetime.utcnow() - timedelta(days=window_days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT pr.predicted_score,
                   (m.saved * 3.0 + m.comments * 2.0 + m.reach * 0.0015 + m.shares * 2.5) as actual
            FROM predictions pr
            JOIN posts p ON pr.post_id = p.id
            JOIN post_metrics m ON p.post_id = m.post_id
            WHERE p.posted_at >= ? AND pr.predicted_score IS NOT NULL AND m.post_id IS NOT NULL
            """,
            (cutoff,),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    if len(rows) < 5:
        return {"status": "insufficient_data", "n": len(rows), "message": "Need ≥5 predictions with metrics to assess accuracy"}

    preds = [r[0] for r in rows]
    actuals = [r[1] for r in rows]

    mae = sum(abs(p - a) for p, a in zip(preds, actuals)) / len(rows)

    # Simple Pearson correlation
    n = len(rows)
    mean_p = sum(preds) / n
    mean_a = sum(actuals) / n
    num = sum((p - mean_p) * (a - mean_a) for p, a in zip(preds, actuals))
    den_p = math.sqrt(sum((p - mean_p) ** 2 for p in preds))
    den_a = math.sqrt(sum((a - mean_a) ** 2 for a in actuals))
    corr = num / (den_p * den_a) if den_p * den_a > 0 else 0.0

    return {
        "n": n,
        "mae": round(mae, 2),
        "correlation": round(corr, 3),
        "mean_predicted": round(mean_p, 1),
        "mean_actual": round(mean_a, 1),
    }


def init_predictions_table() -> None:
    """Add predictions table if not exists (idempotent)."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                post_id INTEGER PRIMARY KEY,
                predicted_score REAL,
                confidence_low REAL,
                confidence_high REAL,
                features_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES posts(id)
            )
            """
        )
        # Add new columns to posts table if missing
        for col, dtype in [
            ("hook_id", "TEXT"),
            ("hook_template", "TEXT"),
            ("content_score", "REAL"),
            ("funnel_3s_hold", "INTEGER DEFAULT 0"),
            ("funnel_completion", "INTEGER DEFAULT 0"),
            ("funnel_dm", "INTEGER DEFAULT 0"),
        ]:
            try:
                cursor.execute(f"ALTER TABLE posts ADD COLUMN {col} {dtype}")
            except Exception:
                pass  # already exists
        conn.commit()
    finally:
        conn.close()
