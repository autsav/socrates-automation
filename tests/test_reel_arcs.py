"""Arc variety: deterministic selection, pure shaping, DB record."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline
from src.core import data_store


def test_pick_arc_rotation_is_deterministic_and_weighted():
    arcs = [pipeline._pick_arc(i) for i in range(8)]
    assert arcs == ["classic", "classic", "question", "cold_open"] * 2
    assert pipeline._pick_arc(None) == "classic"


def test_apply_arc_classic_unchanged():
    h, b = pipeline._apply_arc("classic", "Hook here.", "Bridge here.", "stuck", 1)
    assert (h, b) == ("Hook here.", "Bridge here.")


def test_apply_arc_cold_open_drops_hook_and_bridge():
    h, b = pipeline._apply_arc("cold_open", "Hook here.", "Bridge here.", "stuck", 3)
    assert (h, b) == ("", "")


def test_apply_arc_question_keeps_interrogative_hook():
    h, b = pipeline._apply_arc("question", "What if waiting IS the mistake?", "Bridge.", "stuck", 2)
    assert h.endswith("?")
    assert b == ""


def test_apply_arc_question_replaces_declarative_hook():
    h, b = pipeline._apply_arc("question", "You already know what to do.", "Bridge.", "stuck", 2)
    assert h.endswith("?")           # swapped for a question-form hook
    assert b == ""


def test_record_arc_persists(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setattr(data_store, "DB_PATH", db)
    data_store.init_db()
    row = data_store.save_post("Q", "stuck", "calm_stoic", 0, 0, dry_run=False)
    data_store.record_arc(row, "cold_open")
    con = sqlite3.connect(str(db))
    assert con.execute("SELECT arc FROM posts WHERE id=?", (row,)).fetchone()[0] == "cold_open"
    con.close()
