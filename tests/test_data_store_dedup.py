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


def test_migration_idempotent(db):
    db.init_db()  # second run must not error
    conn = db._get_connection()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(posts)")}
    idx = {r[1] for r in conn.execute("PRAGMA index_list(posts)")}
    conn.close()
    assert "post_date" in cols
    assert "ux_posts_slot_day" in idx


def test_save_post_dedup_real(db):
    a = db.save_post("q", "aud", "calm_stoic", 0, 1, dry_run=False)
    b = db.save_post("q2", "aud", "calm_stoic", 0, 1, dry_run=False)
    assert isinstance(a, int)
    assert b is None


def test_save_post_dry_run_exempt(db):
    a = db.save_post("q", "aud", "calm_stoic", 0, 1, dry_run=True)
    b = db.save_post("q", "aud", "calm_stoic", 0, 1, dry_run=True)
    assert isinstance(a, int) and isinstance(b, int)


def test_has_posted_today_sees_claim(db):
    db.save_post("q", "aud", "calm_stoic", 0, 2, dry_run=False)
    assert db.has_posted_today(2) is True
    assert db.has_posted_today(3) is False
