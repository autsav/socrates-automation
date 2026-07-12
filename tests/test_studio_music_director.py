import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio import music_director as md
from studio.types import MusicDirection, MusicPick


class _SeqClient:
    """Returns queued payloads in order; records role per call."""
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.roles = []

    def call(self, role, *a, **k):
        self.roles.append(role)
        return self.payloads.pop(0)


def _ctx():
    return {"quote": "First say to yourself what you would be.",
            "hook": "You've delayed this long enough.", "mood": "dark_philosophical"}


def test_compose_query_returns_direction():
    client = _SeqClient([{
        "search_query": "somber cello adagio", "energy": "low",
        "bpm_range": [55, 65], "instruments": ["cello"], "avoid": ["drums"]}])
    direction = md.compose_query(client, _ctx())
    assert isinstance(direction, MusicDirection)
    assert direction.search_query == "somber cello adagio"
    assert client.roles == ["music_director"]


def test_rank_tracks_returns_pick():
    hits = [{"id": 11, "tags": "cello, sad", "duration": 30},
            {"id": 22, "tags": "drums, epic", "duration": 20}]
    client = _SeqClient([{"track_id": "11", "rationale": "grief fits", "runner_up_id": "22"}])
    pick = md.rank_tracks(client, _ctx(), hits)
    assert isinstance(pick, MusicPick)
    assert pick.track_id == "11"
    assert client.roles == ["music_director"]


def test_select_music_none_without_api_key():
    assert md.select_music(_SeqClient([]), _ctx(), "", "/tmp") is None


def test_select_music_none_when_no_hits(monkeypatch):
    monkeypatch.setattr(md.download_music, "_search_pixabay_music",
                        lambda q, k, per_page=20: [])
    client = _SeqClient([{"search_query": "x", "energy": "low",
                          "bpm_range": [50, 60], "instruments": [], "avoid": []}])
    assert md.select_music(client, _ctx(), "KEY", "/tmp") is None


def test_select_music_downloads_agent_pick(tmp_path, monkeypatch):
    hits = [{"id": 11, "tags": "cello", "duration": 30, "audio": "http://x/a.mp3"},
            {"id": 22, "tags": "drums", "duration": 20, "audio": "http://x/b.mp3"}]
    monkeypatch.setattr(md.download_music, "_search_pixabay_music",
                        lambda q, k, per_page=20: hits)
    captured = {}

    def fake_dl(url, output_path):
        captured["url"] = url
        Path(output_path).write_bytes(b"ID3fake")
        return True

    monkeypatch.setattr(md.download_music, "_download_track", fake_dl)
    client = _SeqClient([
        {"search_query": "cello", "energy": "low", "bpm_range": [50, 60],
         "instruments": ["cello"], "avoid": []},
        {"track_id": "11", "rationale": "grief fits", "runner_up_id": "22"},
    ])
    out = md.select_music(client, _ctx(), "KEY", tmp_path)
    assert out is not None and Path(out).exists()
    assert captured["url"] == "http://x/a.mp3"  # the id=11 track the agent picked


def test_select_music_unknown_id_falls_back_to_heuristic(tmp_path, monkeypatch):
    hits = [{"id": 11, "tags": "cello", "duration": 30, "audio": "http://x/a.mp3"}]
    monkeypatch.setattr(md.download_music, "_search_pixabay_music",
                        lambda q, k, per_page=20: hits)
    monkeypatch.setattr(md.download_music, "_load_cache", lambda: {})
    picked = {}
    monkeypatch.setattr(md.download_music, "_pick_from_pool",
                        lambda h, mood, cache, pool_size=3: (picked.setdefault("used", True), h[0])[1])
    monkeypatch.setattr(md.download_music, "_download_track",
                        lambda url, output_path: (Path(output_path).write_bytes(b"ID3x"), True)[1])
    client = _SeqClient([
        {"search_query": "cello", "energy": "low", "bpm_range": [50, 60],
         "instruments": [], "avoid": []},
        {"track_id": "999", "rationale": "not in list"},  # unknown id
    ])
    out = md.select_music(client, _ctx(), "KEY", tmp_path)
    assert out is not None
    assert picked.get("used") is True  # heuristic fallback ran


def test_select_music_malformed_hit_in_heuristic_fallback_does_not_raise(tmp_path, monkeypatch):
    """A malformed Pixabay hit (non-numeric 'downloads') must not blow up
    _pick_from_pool's arithmetic and propagate out of select_music — the
    docstring promises select_music 'Never raises'."""
    hits = [{"id": 11, "tags": "cello", "duration": 30, "audio": "http://x/a.mp3",
             "downloads": "lots", "likes": "many"}]
    monkeypatch.setattr(md.download_music, "_search_pixabay_music",
                        lambda q, k, per_page=20: hits)
    # _pick_from_pool and _load_cache are NOT monkeypatched — the real
    # implementation runs and raises TypeError on the malformed hit.
    client = _SeqClient([
        {"search_query": "cello", "energy": "low", "bpm_range": [50, 60],
         "instruments": [], "avoid": []},
        {"track_id": "999", "rationale": "not in list"},  # unknown id -> heuristic path
    ])
    out = md.select_music(client, _ctx(), "KEY", tmp_path)
    assert out is None
