"""Token watchdog — proactive age warning + reactive dead-token alert.

The A4 security scrub means CI always runs on the static GH-secret token, which
silently ages to death at 60 days (exactly what killed auto-posting on Jul 17).
The watchdog tracks the token's first-seen date by fingerprint (no secret
stored) and alerts Telegram before expiry and the moment Meta rejects it."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import token_watchdog as tw


def _iso(days_ago):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def test_fingerprint_is_stable_and_not_the_token():
    fp = tw._fingerprint("EAAsecret-token-value")
    assert fp == tw._fingerprint("EAAsecret-token-value")
    assert "EAAsecret" not in fp
    assert len(fp) == 12


def test_first_sight_records_and_persists(tmp_path, monkeypatch):
    monkeypatch.setattr(tw, "STATE_PATH", tmp_path / "token_meta.json")
    st = tw.check_token_age("tokA")
    assert st["age_days"] == 0
    data = json.loads((tmp_path / "token_meta.json").read_text())
    assert data["fingerprint"] == tw._fingerprint("tokA")


def test_new_token_resets_age(tmp_path, monkeypatch):
    monkeypatch.setattr(tw, "STATE_PATH", tmp_path / "token_meta.json")
    (tmp_path / "token_meta.json").write_text(json.dumps(
        {"fingerprint": tw._fingerprint("OLD"), "first_seen": _iso(55)}))
    st = tw.check_token_age("NEW-token")
    assert st["age_days"] == 0                      # rotation detected


def test_old_token_warns(tmp_path, monkeypatch):
    monkeypatch.setattr(tw, "STATE_PATH", tmp_path / "token_meta.json")
    (tmp_path / "token_meta.json").write_text(json.dumps(
        {"fingerprint": tw._fingerprint("tokA"), "first_seen": _iso(52)}))
    st = tw.check_token_age("tokA")
    assert st["age_days"] == 52
    assert st["warn"] is True                       # >= 60 - 10 threshold
    assert "8" in st["message"] or "days" in st["message"]


def test_fresh_token_no_warn(tmp_path, monkeypatch):
    monkeypatch.setattr(tw, "STATE_PATH", tmp_path / "token_meta.json")
    (tmp_path / "token_meta.json").write_text(json.dumps(
        {"fingerprint": tw._fingerprint("tokA"), "first_seen": _iso(10)}))
    st = tw.check_token_age("tokA")
    assert st["warn"] is False


def test_probe_dead_token_alerts(monkeypatch):
    class _R:
        status_code = 400
        def json(self):
            return {"error": {"code": 190, "message": "Session has expired"}}
    monkeypatch.setattr(tw.requests, "get", lambda *a, **k: _R())
    alive, msg = tw.probe_token("dead", "17841400000000000")
    assert alive is False
    assert "expired" in msg.lower() or "190" in msg


def test_probe_live_token(monkeypatch):
    class _R:
        status_code = 200
        def json(self):
            return {"id": "17841400000000000"}
    monkeypatch.setattr(tw.requests, "get", lambda *a, **k: _R())
    alive, msg = tw.probe_token("live", "17841400000000000")
    assert alive is True
