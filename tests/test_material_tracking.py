"""material_key: recorded per post, feeds the exclusion window (spec 3)."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import data_store


def _use_tmp_db(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setattr(data_store, "DB_PATH", db, raising=False)
    data_store.init_db()
    return db


def test_migration_and_roundtrip(tmp_path, monkeypatch):
    db = _use_tmp_db(tmp_path, monkeypatch)
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO posts (id, quote_text, audience, mood, dry_run) "
        "VALUES (1, 'q', 'a', 'm', 0)"
    )
    con.commit()
    con.close()
    data_store.record_material(1, "zeno-shipwreck")
    data_store.record_material(1, None)          # no-op, never raises
    keys = data_store.recent_material_keys(limit=20)
    assert "zeno-shipwreck" in keys


def test_recent_limits_to_last_n(tmp_path, monkeypatch):
    db = _use_tmp_db(tmp_path, monkeypatch)
    con = sqlite3.connect(db)
    for i in range(30):
        con.execute(
            "INSERT INTO posts (id, quote_text, audience, mood, dry_run, material_key) "
            "VALUES (?, 'q', 'a', 'm', 1, ?)",
            (i + 1, f"k{i}"),
        )
    con.commit()
    con.close()
    keys = data_store.recent_material_keys(limit=20)
    assert len(keys) == 20 and "k29" in keys and "k5" not in keys
