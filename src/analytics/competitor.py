"""
Point 43: Competitor Benchmarking.

Tracks 3 competitor accounts weekly:
  - follower growth estimate
  - post frequency
  - engagement rate estimate
  - top post format

No API scraping — this module generates Telegram-friendly report prompts
for manual data entry + stores them in SQLite for trend tracking.
"""

import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent.parent / "data" / "pipeline.db"

_DEFAULT_COMPETITORS = [
    "dailystoic",
    "stoicquotespage",
    "philosophybreak",
]


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_table() -> None:
    conn = _get_conn()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS competitor_data (
                handle TEXT NOT NULL,
                recorded_week TEXT NOT NULL,
                followers INTEGER DEFAULT 0,
                post_count_week INTEGER DEFAULT 0,
                avg_likes INTEGER DEFAULT 0,
                avg_comments INTEGER DEFAULT 0,
                top_format TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                PRIMARY KEY (handle, recorded_week)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def save_competitor_snapshot(
    handle: str,
    followers: int,
    post_count_week: int,
    avg_likes: int,
    avg_comments: int,
    top_format: str = "",
    notes: str = "",
    week: str = "",
) -> None:
    """Record a weekly competitor snapshot."""
    _ensure_table()
    if not week:
        week = datetime.now().strftime("%Y-W%W")
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO competitor_data
            (handle, recorded_week, followers, post_count_week, avg_likes, avg_comments, top_format, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (handle.lstrip("@"), week, followers, post_count_week, avg_likes, avg_comments, top_format, notes),
        )
        conn.commit()
    finally:
        conn.close()


def get_competitor_report(weeks: int = 4) -> list[dict]:
    """Return recent competitor snapshots for trend analysis."""
    _ensure_table()
    conn = _get_conn()
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT handle, recorded_week, followers, post_count_week,
                   avg_likes, avg_comments, top_format
            FROM competitor_data
            ORDER BY handle, recorded_week DESC
            """,
        )
        rows = [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
    return rows


def generate_benchmark_prompt(our_followers: int = 0, our_avg_likes: int = 0) -> str:
    """
    Generate a Telegram message prompting the user to manually enter
    competitor data for the week.
    """
    week = datetime.now().strftime("%Y-W%W")
    lines = [
        f"📊 WEEKLY COMPETITOR BENCHMARK — {week}",
        "",
        "Manually check these accounts and reply with their stats:",
        "",
    ]
    for handle in _DEFAULT_COMPETITORS:
        lines.append(f"@{handle}:")
        lines.append("  Followers: ???")
        lines.append("  Posts this week: ???")
        lines.append("  Top post likes: ???")
        lines.append("")

    if our_followers or our_avg_likes:
        lines.extend([
            "Our account:",
            f"  Followers: {our_followers:,}",
            f"  Avg likes: {our_avg_likes:,}",
        ])
    return "\n".join(lines)
