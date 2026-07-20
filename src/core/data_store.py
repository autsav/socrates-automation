"""
SQLite state store for pipeline posts, metrics, A/B results, and token state.
WAL mode enabled for concurrent reader/writer safety.
All public functions use try/finally to prevent connection leaks.
"""

import atexit
import os
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path(__file__).parent.parent.parent / "data" / "pipeline.db"


def scrub_committed_tokens(db_path=None) -> None:
    """Remove ALL tokens from the (git-tracked) DB so secrets can never be
    committed. The Meta token is always re-seeded from the META_ACCESS_TOKEN env
    secret by init_db(), and other service tokens are fetched on-demand, so this
    loses nothing operationally. Best-effort — never raises.
    Canonical scrubber for both CI (pre-commit) and the atexit guard below."""
    path = db_path or DB_PATH
    try:
        conn = sqlite3.connect(str(path))
        conn.execute("DELETE FROM token_state")
        conn.commit()
        conn.close()
    except Exception:
        pass


def _scrub_meta_token_on_exit() -> None:
    """Defense-in-depth: after any real process exits, wipe the token from the
    on-disk DB so a stray `git add data/pipeline.db` can't leak it. Skipped under
    pytest (must not touch test DBs / churn the tracked one) and when
    KEEP_META_TOKEN is set (e.g. a workflow that persists a refreshed token)."""
    if "pytest" in sys.modules or os.getenv("KEEP_META_TOKEN"):
        return
    scrub_committed_tokens()


atexit.register(_scrub_meta_token_on_exit)


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
                dry_run BOOLEAN DEFAULT FALSE,
                hook_id TEXT DEFAULT NULL,
                post_date TEXT DEFAULT (date('now')),
                seed INTEGER DEFAULT NULL
            )
        """)

        # Migration: add hook_id to posts tables created before this column existed.
        cursor.execute("PRAGMA table_info(posts)")
        post_columns = {row[1] for row in cursor.fetchall()}
        if "hook_id" not in post_columns:
            cursor.execute("ALTER TABLE posts ADD COLUMN hook_id TEXT DEFAULT NULL")

        # Migration: add post_date + a partial unique index so the dedup guard
        # is atomic (first-writer-wins per day/slot for real posts). SQLite
        # forbids a non-constant DEFAULT on ADD COLUMN, so the column is added
        # nullable and save_post sets post_date=date('now') explicitly.
        if "post_date" not in post_columns:
            cursor.execute("ALTER TABLE posts ADD COLUMN post_date TEXT")
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_posts_slot_day "
            "ON posts(post_date, posting_slot) WHERE dry_run = 0"
        )

        # Migration: add seed (image reproducibility) to older posts tables.
        if "seed" not in post_columns:
            cursor.execute("ALTER TABLE posts ADD COLUMN seed INTEGER DEFAULT NULL")

        # Migration: optimizer A/B attribution — which prompt version(s) produced
        # this post, as a JSON map {optimizer_key: version_id}. Lets the optimizer
        # bucket engagement by champion vs challenger arm (critique B1).
        if "opt_versions_json" not in post_columns:
            cursor.execute("ALTER TABLE posts ADD COLUMN opt_versions_json TEXT DEFAULT NULL")

        # Migration: funnel trigger keyword — the Comment 'X' keyword this post's
        # CTA asks for, so funnel_worker knows what to match in the comments.
        if "trigger_keyword" not in post_columns:
            cursor.execute("ALTER TABLE posts ADD COLUMN trigger_keyword TEXT DEFAULT NULL")

        # Migration: reel arc variant (classic/question/cold_open) — recorded so
        # the optimizer's bandit can learn which structure performs (policy.arc).
        if "arc" not in post_columns:
            cursor.execute("ALTER TABLE posts ADD COLUMN arc TEXT DEFAULT NULL")

        # Migration: material_key — which weird-story capsule / debate topic /
        # trend fed this reel, so we can exclude the last N from re-selection
        # and stop the same anecdote from repeating (spec 3).
        if "material_key" not in post_columns:
            cursor.execute("ALTER TABLE posts ADD COLUMN material_key TEXT DEFAULT NULL")

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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                slot INTEGER NOT NULL,
                quote_row INTEGER,
                audience TEXT,
                format TEXT,
                decision_json TEXT NOT NULL,
                status TEXT DEFAULT 'proposed',
                post_id TEXT
            )
        """)

        # Seed the "meta" token_state row from env on first run, so
        # get_valid_token_with_fallback() has a row to check and the
        # auto-refresh path actually activates instead of always
        # falling through to the raw env token.
        cursor.execute("SELECT 1 FROM token_state WHERE service = 'meta'")
        if cursor.fetchone() is None:
            env_token = os.getenv("META_ACCESS_TOKEN", "")
            if env_token:
                seed_expiry = (datetime.utcnow() + timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO token_state (service, token, expires_at) VALUES (?, ?, ?)",
                    ("meta", env_token, seed_expiry),
                )

        conn.commit()
    finally:
        conn.close()


def record_arc(row_id: int, arc: str | None) -> None:
    """Record which reel arc variant produced this post. Best-effort; never raises."""
    if not arc:
        return
    conn = _get_connection()
    try:
        conn.execute("UPDATE posts SET arc = ? WHERE id = ?", (arc, row_id))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def record_material(row_id: int, key: str | None) -> None:
    """Record which weird-story capsule / debate topic / trend fed this post
    (material_key), so recent_material_keys() can exclude it from re-selection.
    Best-effort; never raises."""
    if not key:
        return
    conn = _get_connection()
    try:
        conn.execute("UPDATE posts SET material_key = ? WHERE id = ?", (key, row_id))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def recent_material_keys(limit: int = 20) -> set[str]:
    """Return the last `limit` non-null material_keys used, most-recent posts
    first (by rowid). Used to exclude recently-used material from re-selection
    (spec 3). Best-effort; returns an empty set on any failure."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT material_key FROM posts WHERE material_key IS NOT NULL "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return {row[0] for row in cursor.fetchall()}
    except Exception:
        return set()
    finally:
        conn.close()


def record_trigger_keyword(row_id: int, keyword: str | None) -> None:
    """Register the post's comment-trigger keyword (e.g. 'RESET') for the
    funnel_worker to match against comments. Best-effort; never raises."""
    if not keyword:
        return
    conn = _get_connection()
    try:
        conn.execute("UPDATE posts SET trigger_keyword = ? WHERE id = ?",
                     (keyword.upper(), row_id))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def record_post_versions(row_id: int, versions: dict) -> None:
    """Store which optimizer prompt version(s) produced a post, as a JSON map
    {key: version_id}, for A/B attribution. Best-effort; never raises."""
    import json as _json
    if not versions:
        return
    conn = _get_connection()
    try:
        conn.execute("UPDATE posts SET opt_versions_json = ? WHERE id = ?",
                     (_json.dumps(versions), row_id))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def save_post(
    quote_text: str,
    audience: str,
    mood: str,
    caption_variant: int,
    posting_slot: int,
    dry_run: bool = False,
    hook_id: str | None = None,
    seed: int | None = None,
) -> int | None:
    """Atomically claim + insert a post record for (today, posting_slot).

    Returns the new row id, or None when a non-dry-run post for this slot was
    already claimed today (the partial unique index fired). dry_run inserts are
    exempt from the guard and always return an id.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO posts
              (quote_text, audience, mood, caption_variant, posting_slot,
               posted_at, dry_run, hook_id, post_date, seed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, date('now'), ?)
            ON CONFLICT(post_date, posting_slot) WHERE dry_run = 0 DO NOTHING
            """,
            (quote_text, audience, mood, caption_variant, posting_slot,
             None, dry_run, hook_id, seed),
        )
        inserted = cursor.rowcount == 1
        conn.commit()
        return cursor.lastrowid if inserted else None
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


def release_post(row_id: int) -> None:
    """Delete a claimed-but-unpublished post so the slot can be retried.

    Called when the publish step fails after save_post already claimed the
    slot. Without this, has_posted_today() blocks all retries for the rest
    of the day (B5 fix). Best-effort — never raises.
    """
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM posts WHERE id = ? AND post_id IS NULL", (row_id,))
        conn.commit()
    except Exception:
        pass
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
            WHERE post_date = date('now')
              AND posting_slot = ?
              AND dry_run = 0
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


def save_proposal(slot, quote_row, audience, fmt, decision_json):
    """Insert a studio proposal. Returns row id."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO proposals (slot, quote_row, audience, format, decision_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (slot, quote_row, audience, fmt, decision_json),
        )
        rid = cur.lastrowid
        conn.commit()
        return rid
    finally:
        conn.close()


def proposed_today(slot):
    """Return True if a proposal already exists for today and this slot."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM proposals WHERE created_at >= date('now') AND slot = ? LIMIT 1",
            (slot,),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def mark_proposal_posted(proposal_id, post_id):
    """Mark a proposal as posted and store its real Instagram post_id."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE proposals SET status='posted', post_id=? WHERE id=?",
            (post_id, proposal_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_pending_proposals():
    """Return proposals still awaiting reconciliation (status='proposed', no post_id)."""
    conn = _get_connection()
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM proposals WHERE status='proposed' AND post_id IS NULL")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def aggregate_performance(window_days=90):
    """Compact per-dimension performance stats for the Analyst (no raw rows)."""
    cutoff = (datetime.utcnow() - timedelta(days=window_days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = _get_connection()
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT p.mood, p.audience, p.posting_slot,
                   COALESCE(m.likes, 0) likes, COALESCE(m.reach, 0) reach,
                   COALESCE(m.saved, 0) saved, COALESCE(m.comments, 0) comments
            FROM posts p LEFT JOIN post_metrics m ON p.post_id = m.post_id
            WHERE p.post_id IS NOT NULL AND p.posted_at >= ?
            """,
            (cutoff,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    def _avg(items, key):
        vals = [r[key] for r in items]
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    def _group(field):
        out = {}
        for k in {r[field] for r in rows}:
            sub = [r for r in rows if r[field] == k]
            out[str(k)] = {"n": len(sub), "avg_reach": _avg(sub, "reach"),
                           "avg_saved": _avg(sub, "saved")}
        return out

    return {
        "sample_size": len(rows),
        "window_days": window_days,
        "overall_avg_reach": _avg(rows, "reach"),
        "overall_avg_saved": _avg(rows, "saved"),
        "by_mood": _group("mood"),
        "by_audience": _group("audience"),
        "by_slot": _group("posting_slot"),
    }


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


# ── Point 31: Repost Strategy (30-day remix) ─────────────────────────────────

def get_top_performers(limit: int = 5, metric: str = "saved") -> list[dict]:
    """
    Point 31: Return top-performing posts by metric (saved | reach | likes).
    Used to identify candidates for 30-day remixes.
    """
    valid = {"saved", "reach", "likes", "comments"}
    col = metric if metric in valid else "saved"

    conn = _get_connection()
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT
                p.id, p.post_id, p.quote_text, p.mood, p.audience,
                p.posted_at, m.saved, m.reach, m.likes, m.comments
            FROM posts p
            JOIN post_metrics m ON p.post_id = m.post_id
            WHERE p.post_id IS NOT NULL AND p.dry_run = FALSE
            ORDER BY m.{col} DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_posts_due_for_remix(days_old: int = 30, limit: int = 3) -> list[dict]:
    """
    Point 31: Find top posts that are ~30 days old and due for a remix.
    Returns posts posted 28-35 days ago sorted by performance.
    """
    conn = _get_connection()
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                p.post_id, p.quote_text, p.mood, p.audience, p.posted_at,
                COALESCE(m.saved, 0) AS saved, COALESCE(m.reach, 0) AS reach
            FROM posts p
            LEFT JOIN post_metrics m ON p.post_id = m.post_id
            WHERE p.dry_run = FALSE
              AND p.posted_at BETWEEN
                datetime('now', ?) AND datetime('now', ?)
            ORDER BY saved DESC
            LIMIT ?
            """,
            (f"-{days_old + 5} days", f"-{days_old - 5} days", limit),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


# ── Point 37: Engagement Pod System ──────────────────────────────────────────

def save_engagement_pod_member(handle: str, notes: str = "") -> None:
    """Point 37: Track an Instagram handle as a pod member."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS engagement_pod (
                handle TEXT PRIMARY KEY,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT DEFAULT ''
            )
            """
        )
        cursor.execute(
            "INSERT OR IGNORE INTO engagement_pod (handle, notes) VALUES (?, ?)",
            (handle.lstrip("@"), notes),
        )
        conn.commit()
    finally:
        conn.close()


def get_engagement_pod() -> list[str]:
    """Point 37: Return list of pod member handles."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS engagement_pod (handle TEXT PRIMARY KEY, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, notes TEXT DEFAULT '')")
        cursor.execute("SELECT handle FROM engagement_pod ORDER BY added_at")
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


# ── Point 40: Engagement Contests ────────────────────────────────────────────

def save_contest_participant(handle: str, post_id: str, week: str = "") -> None:
    """Point 40: Track contest participants (tagged users)."""
    if not week:
        week = datetime.now().strftime("%Y-W%W")
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS contest_participants (
                handle TEXT NOT NULL,
                post_id TEXT NOT NULL,
                week TEXT NOT NULL,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (handle, week)
            )
            """
        )
        cursor.execute(
            "INSERT OR IGNORE INTO contest_participants (handle, post_id, week) VALUES (?, ?, ?)",
            (handle.lstrip("@"), post_id, week),
        )
        conn.commit()
    finally:
        conn.close()


def get_weekly_contest_participants(week: str = "") -> list[dict]:
    """Point 40: Return this week's contest participants."""
    if not week:
        week = datetime.now().strftime("%Y-W%W")
    conn = _get_connection()
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS contest_participants (handle TEXT NOT NULL, post_id TEXT NOT NULL, week TEXT NOT NULL, recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (handle, week))")
        cursor.execute("SELECT handle, post_id, week FROM contest_participants WHERE week = ?", (week,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

