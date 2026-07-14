"""B1: the A/B evaluation engine — bucket engagement by champion/challenger arm
from posts.opt_versions_json and decide, end-to-end on a fixture DB."""
import json
import sqlite3
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimizer import registry, experiments, loop


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "t.db"
    registry.init_optimizer_db(p)
    # Minimal posts + post_metrics tables (subset of data_store's schema).
    con = sqlite3.connect(str(p))
    con.executescript("""
        CREATE TABLE posts (id INTEGER PRIMARY KEY AUTOINCREMENT, post_id TEXT,
                            opt_versions_json TEXT);
        CREATE TABLE post_metrics (post_id TEXT PRIMARY KEY, likes INT, comments INT,
                            shares INT, reach INT, saved INT);
    """)
    con.commit()
    con.close()
    registry.register_asset("k", "prompt", "A {x}", p)
    return p


def _open_exp(db):
    champ = registry.get_champion("k", db)["id"]
    chal = registry.add_version("k", "B {x}", "critic", "sharper", 0.2, db_path=db)
    eid = experiments.open_experiment("k", champ, chal, db_path=db)
    return eid, champ, chal


def _post(db, pid, version_id, saved, reach=100):
    con = sqlite3.connect(str(db))
    con.execute("INSERT INTO posts (post_id, opt_versions_json) VALUES (?,?)",
                (pid, json.dumps({"k": version_id})))
    con.execute("INSERT INTO post_metrics (post_id, likes, comments, shares, reach, saved) "
                "VALUES (?,0,0,0,?,?)", (pid, reach, saved))
    con.commit()
    con.close()


def test_challenger_win_becomes_proposal(db):
    eid, champ, chal = _open_exp(db)
    for i in range(8):
        _post(db, f"c{i}", champ, saved=2)     # champion arm: low saves
        _post(db, f"h{i}", chal, saved=20)     # challenger arm: high saves
    wins = loop.evaluate_experiments(db_path=db, min_samples=8)
    assert len(wins) == 1
    assert wins[0]["challenger_version_id"] == chal
    assert "A/B:" in wins[0]["rationale"]
    # experiment marked data_win (pending human approval), not auto-promoted
    con = sqlite3.connect(str(db))
    status = con.execute("SELECT status FROM opt_experiments WHERE id=?", (eid,)).fetchone()[0]
    con.close()
    assert status == "data_win"
    assert registry.get_champion("k", db)["value"] == "A {x}"   # champion unchanged


def test_challenger_loss_auto_retires(db):
    eid, champ, chal = _open_exp(db)
    for i in range(8):
        _post(db, f"c{i}", champ, saved=20)    # champion better
        _post(db, f"h{i}", chal, saved=2)
    wins = loop.evaluate_experiments(db_path=db, min_samples=8)
    assert wins == []
    assert registry.get_version(chal, db)["status"] == "retired"
    con = sqlite3.connect(str(db))
    status = con.execute("SELECT status FROM opt_experiments WHERE id=?", (eid,)).fetchone()[0]
    con.close()
    assert status == "retired"


def test_insufficient_data_leaves_open(db):
    eid, champ, chal = _open_exp(db)
    _post(db, "c0", champ, saved=2)
    _post(db, "h0", chal, saved=20)            # only 1 per arm
    wins = loop.evaluate_experiments(db_path=db, min_samples=8)
    assert wins == []
    assert experiments.get_open_experiment("k", db)["id"] == eid   # still open


def test_data_win_can_be_approved_and_promotes(db):
    eid, champ, chal = _open_exp(db)
    for i in range(8):
        _post(db, f"c{i}", champ, saved=2)
        _post(db, f"h{i}", chal, saved=20)
    loop.evaluate_experiments(db_path=db, min_samples=8)   # -> data_win
    assert loop.apply_decision(chal, True, db) == "promoted"
    assert registry.get_champion("k", db)["value"] == "B {x}"
