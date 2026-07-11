import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import src.core.token_manager as tm
import src.core.data_store as ds


def test_refresh_skips_network_without_creds(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network must not be called when creds are absent")
    monkeypatch.setattr(tm.requests, "post", boom)
    assert tm.refresh_if_needed("tok123", app_id="", app_secret="", expires_at=None) == "tok123"


def test_init_db_seeds_token_with_expiry(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setenv("META_ACCESS_TOKEN", "seedtok")
    ds.init_db()
    state = ds.get_token("meta")
    assert state is not None and state["expires_at"] is not None


def test_get_valid_token_persists_estimate_when_expiry_missing(monkeypatch):
    saved = {}
    monkeypatch.setattr(ds, "get_token", lambda s: {"token": "tok", "expires_at": None})
    monkeypatch.setattr(ds, "save_token", lambda s, t, e=None: saved.update(service=s, token=t, expires=e))

    class Cfg:
        META_APP_ID = ""
        META_APP_SECRET = ""
        META_ACCESS_TOKEN = "env"

    assert tm.get_valid_token_with_fallback(Cfg()) == "tok"
    assert saved.get("expires") is not None


def test_get_valid_token_does_not_mask_failed_refresh_when_creds_present(monkeypatch):
    saved = {}
    monkeypatch.setattr(ds, "get_token", lambda s: {"token": "tok", "expires_at": None})
    monkeypatch.setattr(ds, "save_token", lambda *a, **k: saved.update(called=True))

    def failing_post(*a, **k):
        raise tm.requests.RequestException("boom")
    monkeypatch.setattr(tm.requests, "post", failing_post)

    class Cfg:
        META_APP_ID = "id"
        META_APP_SECRET = "secret"
        META_ACCESS_TOKEN = "env"

    assert tm.get_valid_token_with_fallback(Cfg()) == "tok"
    assert "called" not in saved  # must NOT persist an optimistic expiry after a failed refresh
