"""Thompson sampling over arcs on sends-per-reach (spec 2.3)."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analytics import arc_bandit


def _db(tmp_path, n_per_arc):
    p = tmp_path / "t.db"
    db = sqlite3.connect(p)
    db.execute("CREATE TABLE posts (post_id TEXT, arc TEXT, dry_run INT)")
    db.execute("CREATE TABLE post_metrics (post_id TEXT PRIMARY KEY, shares INT, reach INT)")
    i = 0
    for arc, shares in n_per_arc:
        pid = f"p{i}"; i += 1
        db.execute("INSERT INTO posts VALUES (?, ?, 0)", (pid, arc))
        db.execute("INSERT INTO post_metrics VALUES (?, ?, 200)", (pid, shares))
    db.commit(); db.close()
    return p


def test_below_floor_returns_none(tmp_path):
    p = _db(tmp_path, [("weird", 5)] * 5)
    assert arc_bandit.pick(1, True, db_path=p) is None


def test_dominant_arc_wins_most_rows(tmp_path):
    rows = [("weird", 10)] * 12 + [("classic", 0)] * 12   # weird crushes classic
    p = _db(tmp_path, rows)
    picks = [arc_bandit.pick(r, True, db_path=p) for r in range(30)]
    assert picks.count("weird") > picks.count("classic")


def test_deterministic_per_row(tmp_path):
    p = _db(tmp_path, [("weird", 10)] * 12 + [("classic", 0)] * 12)
    assert arc_bandit.pick(7, True, db_path=p) == arc_bandit.pick(7, True, db_path=p)
