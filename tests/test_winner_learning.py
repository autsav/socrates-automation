"""The writer studies its own hits once >=3 scripts have sends data (spec 5)."""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import data_store
from src.analytics.performance_digest import winning_scripts


def _seed(db_path, n_scored):
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY, "
                "post_id TEXT, dry_run INT, script_json TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS post_metrics (post_id TEXT PRIMARY KEY, "
                "shares INT, reach INT)")
    for i in range(n_scored):
        s = json.dumps({"hook": f"hook{i}", "reframe": "r " * 80, "cta": f"cta{i}"})
        con.execute("INSERT INTO posts (id, post_id, dry_run, script_json) "
                    "VALUES (?, ?, 0, ?)", (i + 1, f"p{i}", s))
        con.execute("INSERT INTO post_metrics VALUES (?, ?, 300)", (f"p{i}", i * 3))
    con.commit(); con.close()


def test_below_three_scored_returns_empty(tmp_path):
    db = tmp_path / "t.db"; _seed(db, 2)
    assert winning_scripts(db_path=db) == []


def test_top_two_by_sends(tmp_path):
    db = tmp_path / "t.db"; _seed(db, 5)
    w = winning_scripts(n=2, db_path=db)
    assert [x["hook"] for x in w] == ["hook4", "hook3"]
    assert all("sends_per_reach" in x for x in w)


def test_record_script_roundtrip(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setattr(data_store, "DB_PATH", db, raising=False)
    data_store.init_db()
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO posts (id, quote_text, audience, mood, dry_run) "
        "VALUES (1, 'q', 'a', 'm', 0)"
    )
    con.commit()
    con.close()
    data_store.record_script(1, {"hook": "h"})
    data_store.record_script(1, None)          # no-op, never raises
    con = sqlite3.connect(db)
    row = con.execute("SELECT script_json FROM posts WHERE id = 1").fetchone()
    con.close()
    assert json.loads(row[0]) == {"hook": "h"}


def test_empty_reframe_scripts_excluded(tmp_path):
    db = tmp_path / "t.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE posts (id INTEGER PRIMARY KEY, post_id TEXT, dry_run INT, script_json TEXT)")
    con.execute("CREATE TABLE post_metrics (post_id TEXT PRIMARY KEY, shares INT, reach INT)")
    for i in range(4):
        s = json.dumps({"hook": f"h{i}", "reframe": "" if i == 3 else "words " * 40, "cta": "c"})
        con.execute("INSERT INTO posts VALUES (?, ?, 0, ?)", (i + 1, f"p{i}", s))
        con.execute("INSERT INTO post_metrics VALUES (?, ?, 300)", (f"p{i}", i * 5))
    con.commit(); con.close()
    w = winning_scripts(n=2, db_path=db)
    assert all(x["hook"] != "h3" for x in w)   # top scorer but empty reframe -> excluded
