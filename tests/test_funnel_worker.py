"""T2: funnel_worker — keyword matching, dedup, isolation, tally."""
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.engagement import funnel_worker as fw


class _Cfg:
    META_ACCESS_TOKEN = "tok"


def _mkdb(tmp_path, posts):
    db = tmp_path / "p.db"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE posts (id INTEGER PRIMARY KEY, post_id TEXT, "
                "dry_run INT DEFAULT 0, trigger_keyword TEXT)")
    for p in posts:
        con.execute("INSERT INTO posts (post_id, dry_run, trigger_keyword) VALUES (?,?,?)", p)
    con.commit()
    con.close()
    return db


def _isolate_logs(monkeypatch, tmp_path):
    monkeypatch.setattr(fw, "REPLIED_LOG_PATH", tmp_path / "replied.json")
    monkeypatch.setattr(fw, "FUNNEL_LOG_PATH", tmp_path / "funnel_log.json")


def test_matches_word_boundary_case_insensitive():
    assert fw._matches("RESET", "reset 🙏")
    assert fw._matches("RESET", "Reset please!")
    assert not fw._matches("RESET", "love my presets")
    assert not fw._matches("RESET", "")
    assert not fw._matches("", "reset")


def test_sweep_replies_once_per_matching_comment(tmp_path, monkeypatch):
    _isolate_logs(monkeypatch, tmp_path)
    db = _mkdb(tmp_path, [("IG_1", 0, "RESET")])
    sent = []
    t = fw.run_funnel_sweep(
        _Cfg(), db_path=db,
        fetch=lambda pid, tok: [{"id": "c1", "text": "RESET"},
                                {"id": "c2", "text": "nice post"},
                                {"id": "c3", "text": "reset pls"}],
        reply=lambda cid, msg, tok: sent.append((cid, msg)) or True)
    assert t == {"posts_checked": 1, "comments_matched": 2, "replies_sent": 2}
    assert {c for c, _ in sent} == {"c1", "c3"}
    # second sweep: dedup — nothing new sent
    t2 = fw.run_funnel_sweep(
        _Cfg(), db_path=db,
        fetch=lambda pid, tok: [{"id": "c1", "text": "RESET"},
                                {"id": "c3", "text": "reset pls"}],
        reply=lambda cid, msg, tok: sent.append((cid, msg)) or True)
    assert t2["replies_sent"] == 0
    assert len(sent) == 2


def test_sweep_skips_pending_manual_and_no_keyword(tmp_path, monkeypatch):
    _isolate_logs(monkeypatch, tmp_path)
    db = _mkdb(tmp_path, [("PENDING_MANUAL_7", 0, "RESET"), ("IG_2", 0, None),
                          ("IG_3", 1, "RESET")])   # dry-run excluded too
    t = fw.run_funnel_sweep(_Cfg(), db_path=db,
                            fetch=lambda *a: (_ for _ in ()).throw(AssertionError("no fetch")),
                            reply=lambda *a: True)
    assert t["posts_checked"] == 0


def test_one_bad_post_does_not_stop_sweep(tmp_path, monkeypatch):
    _isolate_logs(monkeypatch, tmp_path)
    db = _mkdb(tmp_path, [("IG_BAD", 0, "RESET"), ("IG_OK", 0, "STOIC")])
    def fetch(pid, tok):
        if pid == "IG_BAD":
            raise RuntimeError("graph down")
        return [{"id": "c9", "text": "STOIC"}]
    t = fw.run_funnel_sweep(_Cfg(), db_path=db, fetch=fetch,
                            reply=lambda cid, msg, tok: True)
    assert t["posts_checked"] == 2
    assert t["replies_sent"] == 1


def test_reply_templates_never_promise_dm():
    for msg in fw.REPLY_TEMPLATES:
        assert not re.search(r"DM('| )?(you|s)", msg, re.I)


def test_missing_token_is_noop_with_tally(tmp_path, monkeypatch):
    _isolate_logs(monkeypatch, tmp_path)
    class _NoTok:
        pass
    t = fw.run_funnel_sweep(_NoTok(), db_path=tmp_path / "missing.db",
                            fetch=lambda *a: [], reply=lambda *a: True)
    assert t["replies_sent"] == 0
    assert json.loads((tmp_path / "funnel_log.json").read_text())  # tally written
