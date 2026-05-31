"""
SQLite state store for pipeline posts, metrics, A/B results, and token state.
WAL mode enabled for concurrent reader/writer safety.
All public functions use try/finally to prevent connection leaks.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path(__file__).parent / "data" / "pipeline.db"


def _get_connection() -> sqlite3.Connection:
    """Return a connection with WAL mode enabled."""
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quote_text TEXT NOT NULL,
                audience TEXT NOT NULL,
                mood TEXT NOT NULL,
                caption_variant INTEGER DEFAULT 0,
                posting_slot INTEGER DEFAULT 0,
                posted_at TIMESTAMP,
                post_id TEXT UNIQUE,
                image_path TEXT,
                reel_path TEXT,
                dry_run BOOLEAN DEFAULT FALSE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS post_metrics (
                post_id TEXT PRIMARY KEY,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                reach INTEGER DEFAULT 0,
                impressions INTEGER DEFAULT 0,
                saved INTEGER DEFAULT 0,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES posts(post_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ab_results (
                dimension TEXT NOT NULL,
                variant_a TEXT NOT NULL,
                variant_b TEXT NOT NULL,
                wins_a INTEGER DEFAULT 0,
                wins_b INTEGER DEFAULT 0,
                trials INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (dimension, variant_a, variant_b)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS token_state (
                service TEXT PRIMARY KEY,
                token TEXT NOT NULL,
                expires_at TIMESTAMP,
                last_refreshed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        conn.close()


def save_post(
    quote_text: str,
    audience: str,
    mood: str,
    caption_variant: int,
    posting_slot: int,
    dry_run: bool = False,
) -> int:
    """Insert a new post record. Returns row id."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO posts (quote_text, audience, mood, caption_variant, posting_slot, posted_at, dry_run)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (quote_text, audience, mood, caption_variant, posting_slot, None, dry_run),
        )
        row_id = cursor.lastrowid
        conn.commit()
        return row_id
    finally:
        conn.close()


def mark_posted(row_id: int, post_id: str, image_path: str, reel_path: str | None = None) -> None:
    """Update post with actual post_id and paths after successful publish."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE posts SET post_id = ?, image_path = ?, reel_path = ?, posted_at = CURRENT_TIMESTAMP WHERE id = ?",
            (post_id, image_path, reel_path, row_id),
        )
        conn.commit()
    finally:
        conn.close()


def _ensure_ab_row(dimension: str, variant_a: str, variant_b: str) -> None:
    """Create an ab_results row if it doesn't exist."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO ab_results (dimension, variant_a, variant_b, wins_a, wins_b, trials)
            VALUES (?, ?, ?, 0, 0, 0)
            """,
            (dimension, variant_a, variant_b),
        )
        conn.commit()
    finally:
        conn.close()


def get_ab_results(dimension: str, variant_a: str, variant_b: str) -> dict:
    """Return wins_a, wins_b, trials for a dimension pair.
    Returns zeroed defaults if no row exists yet."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT wins_a, wins_b, trials FROM ab_results
            WHERE dimension = ? AND variant_a = ? AND variant_b = ?
            """,
            (dimension, variant_a, variant_b),
        )
        row = cursor.fetchone()
        if row is None:
            return {"wins_a": 0, "wins_b": 0, "trials": 0}
        return {"wins_a": row[0], "wins_b": row[1], "trials": row[2]}
    finally:
        conn.close()


def record_ab_win(dimension: str, variant_a: str, variant_b: str, winner: str) -> None:
    """Increment wins for the winning variant."""
    _ensure_ab_row(dimension, variant_a, variant_b)
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        if winner == variant_a:
            cursor.execute(
                """
                UPDATE ab_results
                SET wins_a = wins_a + 1, trials = trials + 1, last_updated = CURRENT_TIMESTAMP
                WHERE dimension = ? AND variant_a = ? AND variant_b = ?
                """,
                (dimension, variant_a, variant_b),
            )
        elif winner == variant_b:
            cursor.execute(
                """
                UPDATE ab_results
                SET wins_b = wins_b + 1, trials = trials + 1, last_updated = CURRENT_TIMESTAMP
                WHERE dimension = ? AND variant_a = ? AND variant_b = ?
                """,
                (dimension, variant_a, variant_b),
            )
        else:
            raise ValueError(f"winner must be '{variant_a}' or '{variant_b}', got '{winner}'")
        conn.commit()
    finally:
        conn.close()


def has_posted_today(slot: int) -> bool:
    """Return True if a non-dry-run post already exists for today and slot."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 1 FROM posts
            WHERE posted_at >= date('now')
              AND posting_slot = ?
              AND dry_run = FALSE
            LIMIT 1
            """,
            (slot,),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def get_last_posted_for_audience(audience: str, days: int = 30) -> list[dict]:
    """Return recent posts for an audience with metrics joined."""
    if not isinstance(days, int) or days < 0:
        raise ValueError("days must be a non-negative integer")
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_connection()
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT p.*, m.likes, m.comments, m.reach, m.impressions
            FROM posts p
            LEFT JOIN post_metrics m ON p.post_id = m.post_id
            WHERE p.audience = ? AND p.posted_at >= ?
            ORDER BY p.posted_at DESC
            """,
            (audience, cutoff),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def save_token(service: str, token: str, expires_at: datetime | None = None) -> None:
    """Store or update a token."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO token_state (service, token, expires_at, last_refreshed)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(service) DO UPDATE SET
                token = excluded.token,
                expires_at = excluded.expires_at,
                last_refreshed = CURRENT_TIMESTAMP
            """,
            (service, token, expires_at.strftime("%Y-%m-%d %H:%M:%S") if expires_at else None),
        )
        conn.commit()
    finally:
        conn.close()


def get_token(service: str) -> dict | None:
    """Return {token, expires_at, last_refreshed} or None."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT token, expires_at, last_refreshed FROM token_state WHERE service = ?",
            (service,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {
            "token": row[0],
            "expires_at": row[1],
            "last_refreshed": row[2],
        }
    finally:
        conn.close()
