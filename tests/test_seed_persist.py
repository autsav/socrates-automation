import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import src.core.data_store as ds


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "DB_PATH", tmp_path / "t.db")
    ds.init_db()
    return ds


def test_seed_column_migration_idempotent(db):
    db.init_db()  # second run must not error
    conn = db._get_connection()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(posts)")}
    conn.close()
    assert "seed" in cols


def test_save_post_persists_seed(db):
    rid = db.save_post("q", "aud", "calm_stoic", 0, 5, dry_run=True, seed=4242)
    conn = db._get_connection()
    val = conn.execute("SELECT seed FROM posts WHERE id = ?", (rid,)).fetchone()[0]
    conn.close()
    assert val == 4242
