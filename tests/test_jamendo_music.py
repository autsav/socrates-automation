import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.audio import jamendo_music as jm


class _Dir:
    def __init__(self, search_query="dark ambient", energy="low"):
        self.search_query = search_query
        self.energy = energy


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


def test_search_tracks_sends_instrumental_and_filters_disallowed(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _Resp({"results": [
            {"id": 1, "name": "ok", "duration": 30, "audiodownload": "http://x/1.mp3",
             "audiodownload_allowed": True},
            {"id": 2, "name": "no", "duration": 30, "audiodownload": "http://x/2.mp3",
             "audiodownload_allowed": False},
        ]})

    monkeypatch.setattr(jm.requests, "get", fake_get)
    hits = jm.search_tracks(_Dir(search_query="dark ambient", energy="low"), "KEY", limit=20)

    assert captured["params"]["vocalinstrumental"] == "instrumental"
    assert captured["params"]["speed"] == "low"
    assert captured["params"]["fuzzytags"] == "dark+ambient"
    assert captured["params"]["client_id"] == "KEY"
    assert [h["id"] for h in hits] == [1]  # disallowed hit filtered out


def test_search_tracks_http_error_returns_empty(monkeypatch):
    def boom(url, params=None, timeout=None):
        raise RuntimeError("network")
    monkeypatch.setattr(jm.requests, "get", boom)
    assert jm.search_tracks(_Dir(), "KEY") == []


def test_search_tracks_no_client_id_returns_empty():
    assert jm.search_tracks(_Dir(), "") == []


def test_extract_meta_flattens_tags():
    hit = {"id": 7, "name": "Cello Piece", "duration": 42,
           "musicinfo": {"tags": {"genres": ["classical"], "instruments": ["cello"]}}}
    meta = jm.extract_meta(hit)
    assert meta["id"] == "7"
    assert meta["duration"] == 42
    assert "cello" in meta["tags"] and "classical" in meta["tags"]


def test_pick_audio_url_respects_allowed():
    assert jm.pick_audio_url({"audiodownload_allowed": True,
                              "audiodownload": "http://x/a.mp3"}) == "http://x/a.mp3"
    assert jm.pick_audio_url({"audiodownload_allowed": False,
                              "audiodownload": "http://x/a.mp3"}) is None
    assert jm.pick_audio_url({"audiodownload_allowed": True, "audiodownload": ""}) is None


def test_download_track_writes_and_validates(tmp_path, monkeypatch):
    class _DL:
        content = b"ID3" + b"\x00" * 60_000
        def raise_for_status(self): pass
    monkeypatch.setattr(jm.requests, "get", lambda url, timeout=None, stream=None: _DL())
    out = tmp_path / "t.mp3"
    assert jm.download_track("http://x/a.mp3", out) is True
    assert out.exists()


def test_download_track_error_returns_false(tmp_path, monkeypatch):
    def boom(url, timeout=None, stream=None):
        raise RuntimeError("nope")
    monkeypatch.setattr(jm.requests, "get", boom)
    assert jm.download_track("http://x/a.mp3", tmp_path / "t.mp3") is False


def test_pick_from_pool_prefers_downloadable_and_longish():
    hits = [
        {"id": 1, "audiodownload_allowed": True, "audiodownload": "http://x/1.mp3", "duration": 8},
        {"id": 2, "audiodownload_allowed": True, "audiodownload": "http://x/2.mp3", "duration": 30},
        {"id": 3, "audiodownload_allowed": False, "audiodownload": "http://x/3.mp3", "duration": 30},
    ]
    assert jm.pick_from_pool(hits)["id"] == 2  # downloadable + duration>=15
    assert jm.pick_from_pool([]) is None
