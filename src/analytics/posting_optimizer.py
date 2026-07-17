"""Optimal posting time analyzer — uses historical engagement data to recommend
the best posting slots by day-of-week and time-of-day.

Analyzes post_metrics joined with posts to find which slots consistently
produce the highest engagement. Falls back to research-backed defaults
when insufficient data exists.
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "pipeline.db"

# Research-backed default engagement by slot (0=morning, 1=afternoon, 2=evening)
# Source: Buffer 2024 study of 9.6M posts + Hootsuite 2025 data
DEFAULT_SLOT_WEIGHTS = {
    0: 0.85,   # 08:00 — morning commute (good)
    1: 0.70,   # 12:00 — lunch break (decent)
    2: 1.00,   # 18:00 — evening peak (best)
}

# Day-of-week weights (1=Mon ... 7=Sun)
DEFAULT_DAY_WEIGHTS = {
    1: 0.90, 2: 0.85, 3: 1.00, 4: 0.95,  # Mon-Thu (Wed best)
    5: 0.75, 6: 0.80, 7: 0.65,            # Fri-Sun (weekends lower for philosophy)
}


def _get_connection():
    return sqlite3.connect(str(DB_PATH), timeout=5)


def get_slot_performance(window_days: int = 90) -> dict:
    """Return avg engagement score per posting slot from historical data.

    Returns {slot: avg_score} for slots 0, 1, 2.
    Falls back to DEFAULT_SLOT_WEIGHTS if insufficient data.
    """
    from src.analytics.score_weights import engagement_score

    cutoff = (datetime.utcnow() - timedelta(days=window_days)).strftime("%Y-%m-%d")
    conn = _get_connection()
    try:
        rows = conn.execute(
            """SELECT p.posting_slot, m.likes, m.comments, m.shares, m.saved, m.reach
               FROM posts p
               LEFT JOIN post_metrics m ON p.post_id = m.post_id
               WHERE p.posted_at >= ? AND p.dry_run = 0
               AND p.post_id IS NOT NULL""",
            (cutoff,)
        ).fetchall()

        slot_scores = {0: [], 1: [], 2: []}
        for row in rows:
            slot = row[0]
            if slot not in slot_scores:
                continue
            metrics = {
                "likes": row[1] or 0, "comments": row[2] or 0,
                "shares": row[3] or 0, "saved": row[4] or 0, "reach": row[5] or 1,
            }
            score = engagement_score(metrics)
            if score > 0:
                slot_scores[slot].append(score)

        result = {}
        for slot, scores in slot_scores.items():
            if len(scores) >= 3:  # Need at least 3 data points
                result[slot] = sum(scores) / len(scores)
            else:
                result[slot] = DEFAULT_SLOT_WEIGHTS.get(slot, 0.75)

        return result
    except Exception:
        return dict(DEFAULT_SLOT_WEIGHTS)
    finally:
        conn.close()


def get_day_performance(window_days: int = 90) -> dict:
    """Return avg engagement score per day-of-week from historical data.

    Returns {day_number: avg_score} (1=Mon ... 7=Sun).
    Falls back to DEFAULT_DAY_WEIGHTS if insufficient data.
    """
    from src.analytics.score_weights import engagement_score

    cutoff = (datetime.utcnow() - timedelta(days=window_days)).strftime("%Y-%m-%d")
    conn = _get_connection()
    try:
        rows = conn.execute(
            """SELECT p.post_date, m.likes, m.comments, m.shares, m.saved, m.reach
               FROM posts p
               LEFT JOIN post_metrics m ON p.post_id = m.post_id
               WHERE p.posted_at >= ? AND p.dry_run = 0
               AND p.post_id IS NOT NULL""",
            (cutoff,)
        ).fetchall()

        day_scores = {i: [] for i in range(1, 8)}
        for row in rows:
            post_date_str = row[0]
            if not post_date_str:
                continue
            try:
                dt = datetime.strptime(post_date_str, "%Y-%m-%d")
                day = dt.isoweekday()  # 1=Mon ... 7=Sun
            except (ValueError, TypeError):
                continue

            metrics = {
                "likes": row[1] or 0, "comments": row[2] or 0,
                "shares": row[3] or 0, "saved": row[4] or 0, "reach": row[5] or 1,
            }
            score = engagement_score(metrics)
            if score > 0:
                day_scores[day].append(score)

        result = {}
        for day, scores in day_scores.items():
            if len(scores) >= 3:
                result[day] = sum(scores) / len(scores)
            else:
                result[day] = DEFAULT_DAY_WEIGHTS.get(day, 0.75)

        return result
    except Exception:
        return dict(DEFAULT_DAY_WEIGHTS)
    finally:
        conn.close()


def recommend_best_slot(date: datetime | None = None) -> tuple[int, str]:
    """Recommend the best posting slot for a given date.

    Combines slot performance + day-of-week performance.
    Returns (slot_number, reason_string).
    """
    if date is None:
        date = datetime.utcnow()

    day_of_week = date.isoweekday()
    slot_perf = get_slot_performance()
    day_perf = get_day_performance()

    # Combined score = slot_weight * day_weight
    best_slot = 0
    best_score = -1
    for slot in range(3):
        combined = slot_perf.get(slot, 0.75) * day_perf.get(day_of_week, 0.75)
        if combined > best_score:
            best_score = combined
            best_slot = slot

    slot_names = {0: "morning (08:00)", 1: "afternoon (15:00)", 2: "evening (18:00)"}
    day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday",
                 5: "Friday", 6: "Saturday", 7: "Sunday"}

    reason = (f"{day_names.get(day_of_week, '?')} {slot_names.get(best_slot, '?')} "
              f"(combined score: {best_score:.2f})")

    return best_slot, reason


def get_optimal_schedule() -> dict:
    """Return a full 7-day optimal posting schedule.

    Returns {day_number: [{"slot": int, "score": float, "reason": str}]}.
    """
    slot_perf = get_slot_performance()
    day_perf = get_day_performance()

    schedule = {}
    day_names = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday",
                 5: "Friday", 6: "Saturday", 7: "Sunday"}
    slot_names = {0: "morning", 1: "afternoon", 2: "evening"}

    for day in range(1, 8):
        slots = []
        for slot in range(3):
            combined = slot_perf.get(slot, 0.75) * day_perf.get(day, 0.75)
            slots.append({
                "slot": slot,
                "time": slot_names[slot],
                "score": round(combined, 3),
            })
        slots.sort(key=lambda x: x["score"], reverse=True)
        schedule[day_names[day]] = slots

    return schedule