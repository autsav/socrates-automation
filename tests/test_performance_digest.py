"""Per-agent digest: agents SEE their own results (spec 2.2).

Schema note: the real `posts` table (src/core/data_store.py:60-76) has no
`hook` or `caption` column. Caption text is never persisted to SQLite (it
lives transiently in-memory / in data/approvals.json — see task-8-report.md).
`quote_text` is the only NOT NULL, always-populated human-readable field, so
it stands in as the hook surrogate (first line, in case of multi-line quotes).
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analytics.performance_digest import build_digest, digest_text


def _db(tmp_path):
    p = tmp_path / "t.db"
    db = sqlite3.connect(p)
    db.execute("CREATE TABLE posts (post_id TEXT, arc TEXT, quote_text TEXT, dry_run INT)")
    db.execute("CREATE TABLE post_metrics (post_id TEXT PRIMARY KEY, shares INT, reach INT)")
    rows = [("p1", "weird", "Barefoot senator.", 9, 300),    # 3.0% -> top
            ("p2", "story", "Airport chaos.", 2, 400),        # 0.5%
            ("p3", "classic", "Plain quote.", 0, 500),        # 0.0% -> bottom
            ("p4", "weird", "Tiny reach.", 50, 50)]           # under floor -> excluded
    for pid, arc, quote_text, sh, re_ in rows:
        db.execute("INSERT INTO posts VALUES (?, ?, ?, 0)", (pid, arc, quote_text))
        db.execute("INSERT INTO post_metrics VALUES (?, ?, ?)", (pid, sh, re_))
    db.commit(); db.close()
    return p


def test_ranks_by_sends_per_reach_with_floor(tmp_path):
    d = build_digest(_db(tmp_path))
    sw = d["story_writer"]
    assert sw[0]["hook"] == "Barefoot senator." and sw[0]["rank"] == "top"
    assert all(e["hook"] != "Tiny reach." for e in sw)


def test_digest_text_cold_start(tmp_path):
    p = tmp_path / "empty.db"
    sqlite3.connect(p).close()
    assert digest_text("story_writer", db_path=p) == "No performance data yet."


def test_digest_text_cold_start_missing_db(tmp_path):
    """No sqlite file at all (never opened) must not raise either."""
    p = tmp_path / "does_not_exist.db"
    assert digest_text("story_writer", db_path=p) == "No performance data yet."


def test_build_digest_missing_tables_returns_empty(tmp_path):
    """A DB file that exists but has no posts/post_metrics tables (true
    cold start against a freshly created file) must return {} not raise."""
    p = tmp_path / "no_tables.db"
    sqlite3.connect(p).close()
    assert build_digest(p) == {}


def test_all_three_agent_views_present(tmp_path):
    d = build_digest(_db(tmp_path))
    assert set(d.keys()) == {"story_writer", "copywriter", "strategist"}
