"""T1: CTA honesty + trigger-keyword registry."""
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline
from src.core import data_store


def test_no_cta_promises_a_dm():
    # The funnel replies publicly; nothing sends DMs. A DM promise is a lie.
    for v in pipeline._CTA_VARIANTS:
        assert not re.search(r"DM('| )?(you|s)", v, re.I), f"CTA promises a DM: {v!r}"


def test_extract_trigger_keyword():
    assert pipeline._extract_trigger_keyword(
        "Comment 'RESET' and I'll point you to the 3-line Stoic reset.") == "RESET"
    assert pipeline._extract_trigger_keyword(
        "Comment 'stoic' for the full reflection.") == "STOIC"
    assert pipeline._extract_trigger_keyword("Save this. You will need it again.") is None
    assert pipeline._extract_trigger_keyword("") is None
    assert pipeline._extract_trigger_keyword(None) is None


def test_migration_adds_trigger_keyword_and_record_writes_it(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setattr(data_store, "DB_PATH", db)
    data_store.init_db()
    row = data_store.save_post("Q", "stuck", "calm_stoic", 0, 0, dry_run=False)
    data_store.record_trigger_keyword(row, "reset")
    con = sqlite3.connect(str(db))
    kw = con.execute("SELECT trigger_keyword FROM posts WHERE id=?", (row,)).fetchone()[0]
    con.close()
    assert kw == "RESET"          # normalized upper


def test_record_trigger_keyword_none_is_noop(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setattr(data_store, "DB_PATH", db)
    data_store.init_db()
    row = data_store.save_post("Q", "stuck", "calm_stoic", 0, 0, dry_run=False)
    data_store.record_trigger_keyword(row, None)   # must not raise
    con = sqlite3.connect(str(db))
    kw = con.execute("SELECT trigger_keyword FROM posts WHERE id=?", (row,)).fetchone()[0]
    con.close()
    assert kw is None
