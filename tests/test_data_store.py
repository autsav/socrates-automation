import sqlite3
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.data_store import init_db, save_post, mark_posted, get_ab_results, record_ab_win, get_last_posted_for_audience, has_posted_today


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    from src.core import data_store
    data_store.DB_PATH = db_path
    init_db()
    return db_path


def test_init_db_creates_tables(db):
    conn = sqlite3.connect(str(db))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert "posts" in tables
    assert "post_metrics" in tables
    assert "ab_results" in tables
    assert "token_state" in tables
    conn.close()


def test_save_post_returns_row_id(db):
    row_id = save_post("Test quote", "stuck", "calm_stoic", 0, 0)
    assert isinstance(row_id, int)
    assert row_id > 0


def test_mark_posted_updates_record(db):
    row_id = save_post("Test quote", "stuck", "calm_stoic", 0, 0)
    mark_posted(row_id, "ig_post_123", "/output/test.jpg", "/output/test.mp4")

    conn = sqlite3.connect(str(db))
    cursor = conn.cursor()
    cursor.execute("SELECT post_id, image_path, reel_path FROM posts WHERE id = ?", (row_id,))
    post_id, image_path, reel_path = cursor.fetchone()
    conn.close()

    assert post_id == "ig_post_123"
    assert image_path == "/output/test.jpg"
    assert reel_path == "/output/test.mp4"


def test_ab_results_roundtrip(db):
    get_ab_results("caption", "hook_first", "story_first")  # creates row implicitly
    record_ab_win("caption", "hook_first", "story_first", "hook_first")
    result = get_ab_results("caption", "hook_first", "story_first")
    assert result["wins_a"] == 1
    assert result["wins_b"] == 0
    assert result["trials"] == 1


def test_has_posted_today_true(db):
    row_id = save_post("Test", "stuck", "calm_stoic", 0, 1, dry_run=False)
    mark_posted(row_id, "ig_123", "/img.jpg")
    assert has_posted_today(1) is True


def test_has_posted_today_false_no_posts(db):
    assert has_posted_today(0) is False


def test_has_posted_today_false_dry_run_only(db):
    row_id = save_post("Test", "stuck", "calm_stoic", 0, 1, dry_run=True)
    mark_posted(row_id, "ig_123", "/img.jpg")
    assert has_posted_today(1) is False


def test_has_posted_today_false_different_slot(db):
    row_id = save_post("Test", "stuck", "calm_stoic", 0, 1, dry_run=False)
    mark_posted(row_id, "ig_123", "/img.jpg")
    assert has_posted_today(2) is False


def test_two_pending_manual_rows_do_not_collide_on_unique_post_id(db):
    # A2 regression: post_id is UNIQUE. Two manual posts previously both wrote
    # the literal "PENDING_MANUAL" → IntegrityError on the 2nd. The per-row
    # sentinel used by pipeline.py must let both coexist.
    r1 = save_post("Q1", "stuck", "calm_stoic", 0, 0, dry_run=False)
    r2 = save_post("Q2", "lost", "calm_stoic", 1, 1, dry_run=False)
    mark_posted(r1, f"PENDING_MANUAL_{r1}", None, "/output/a.mp4")
    mark_posted(r2, f"PENDING_MANUAL_{r2}", None, "/output/b.mp4")   # must not raise
    conn = sqlite3.connect(str(db))
    ids = {row[0] for row in conn.execute("SELECT post_id FROM posts")}
    conn.close()
    assert f"PENDING_MANUAL_{r1}" in ids and f"PENDING_MANUAL_{r2}" in ids
