import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import data_store


def _fresh_db(tmp_path):
    db = tmp_path / "pipeline.db"
    data_store.DB_PATH = db
    data_store.init_db()
    return db


def test_save_and_proposed_today(tmp_path):
    _fresh_db(tmp_path)
    pid = data_store.save_proposal(0, 12, "stuck", "reel", '{"top_pick":"c1"}')
    assert isinstance(pid, int)
    assert data_store.proposed_today(0) is True
    assert data_store.proposed_today(1) is False


def test_mark_posted_and_pending(tmp_path):
    _fresh_db(tmp_path)
    pid = data_store.save_proposal(1, 5, "lazy", "image", "{}")
    assert len(data_store.get_pending_proposals()) == 1
    data_store.mark_proposal_posted(pid, "IG_123")
    assert data_store.get_pending_proposals() == []


def test_aggregate_performance_shape(tmp_path):
    _fresh_db(tmp_path)
    conn = data_store._get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO posts (quote_text,audience,mood,posting_slot,posted_at,post_id) "
                "VALUES ('q','stuck','epic_warrior',0,datetime('now'),'p1')")
    cur.execute("INSERT INTO post_metrics (post_id,likes,reach,saved) VALUES ('p1',10,100,5)")
    conn.commit()
    conn.close()
    stats = data_store.aggregate_performance(window_days=90)
    assert stats["sample_size"] >= 1
    assert "by_mood" in stats and "by_slot" in stats
