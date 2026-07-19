"""Phase-2 poller: posts 1-7 days old get RE-polled (metrics keep moving)."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analytics import metrics


def _seed(db, post_id, days_ago, with_metrics=False):
    db.execute("INSERT INTO posts (post_id, posted_at, dry_run) "
               "VALUES (?, datetime('now', ?), 0)", (post_id, f"-{days_ago} days"))
    if with_metrics:
        db.execute("INSERT INTO post_metrics (post_id, shares, reach) "
                   "VALUES (?, 1, 100)", (post_id,))


def test_window_repolls_and_upserts(tmp_path, monkeypatch):
    db_path = tmp_path / "t.db"
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE posts (post_id TEXT, posted_at TEXT, dry_run INT)")
    db.execute("CREATE TABLE post_metrics (post_id TEXT PRIMARY KEY, likes INT "
               "DEFAULT 0, comments INT DEFAULT 0, shares INT DEFAULT 0, "
               "reach INT DEFAULT 0, impressions INT DEFAULT 0, saved INT DEFAULT 0)")
    _seed(db, "fresh", 2, with_metrics=True)   # has stale metrics -> re-polled
    _seed(db, "old", 12)                        # outside window -> skipped
    db.commit(); db.close()

    monkeypatch.setattr(metrics, "fetch_post_metrics",
                        lambda pid, tok, ig: {"likes": 9, "comments": 1,
                                              "shares": 5, "reach": 200,
                                              "impressions": 250, "saved": 3})
    n = metrics.ingest_window("tok", "ig", db_path=db_path)
    assert n == 1
    row = sqlite3.connect(db_path).execute(
        "SELECT shares, reach FROM post_metrics WHERE post_id='fresh'").fetchone()
    assert row == (5, 200)
