import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio import music_director as md
from studio.types import MusicDirection, MusicPick


class _SeqClient:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.roles = []

    def call(self, role, *a, **k):
        self.roles.append(role)
        return self.payloads.pop(0)


def _ctx():
    return {"quote": "First say to yourself what you would be.",
            "hook": "You've delayed this long enough.", "mood": "dark_philosophical"}


def _hit(i, allowed=True, duration=30):
    return {"id": i, "name": f"track{i}", "duration": duration,
            "audiodownload": f"http://x/{i}.mp3", "audiodownload_allowed": allowed,
            "musicinfo": {"tags": {"instruments": ["cello"]}}}


def test_compose_query_returns_direction():
    client = _SeqClient([{
        "search_query": "somber cello adagio", "energy": "low",
        "bpm_range": [55, 65], "instruments": ["cello"], "avoid": ["drums"]}])
    direction = md.compose_query(client, _ctx())
    assert isinstance(direction, MusicDirection)
    assert direction.search_query == "somber cello adagio"
    assert client.roles == ["music_director"]


def test_rank_tracks_returns_pick():
    hits = [_hit(11), _hit(22)]
    client = _SeqClient([{"track_id": "11", "rationale": "grief fits", "runner_up_id": "22"}])
    pick = md.rank_tracks(client, _ctx(), hits)
    assert isinstance(pick, MusicPick)
    assert pick.track_id == "11"


def test_select_music_none_without_api_key():
    assert md.select_music(_SeqClient([]), _ctx(), "", "/tmp") is None


def test_select_music_none_when_no_hits(monkeypatch):
    monkeypatch.setattr(md.jamendo_music, "search_tracks",
                        lambda direction, client_id, limit=20: [])
    client = _SeqClient([{"search_query": "x", "energy": "low",
                          "bpm_range": [50, 60], "instruments": [], "avoid": []}])
    assert md.select_music(client, _ctx(), "KEY", "/tmp") is None


def test_select_music_downloads_agent_pick(tmp_path, monkeypatch):
    hits = [_hit(11), _hit(22)]
    monkeypatch.setattr(md.jamendo_music, "search_tracks",
                        lambda direction, client_id, limit=20: hits)
    captured = {}

    def fake_dl(url, output_path):
        captured["url"] = url
        Path(output_path).write_bytes(b"ID3fake")
        return True

    monkeypatch.setattr(md.jamendo_music, "download_track", fake_dl)
    client = _SeqClient([
        {"search_query": "cello", "energy": "low", "bpm_range": [50, 60],
         "instruments": ["cello"], "avoid": []},
        {"track_id": "11", "rationale": "grief fits", "runner_up_id": "22"},
    ])
    out = md.select_music(client, _ctx(), "KEY", tmp_path)
    assert out is not None and Path(out).exists()
    assert captured["url"] == "http://x/11.mp3"


def test_select_music_unknown_id_falls_back_to_heuristic(tmp_path, monkeypatch):
    hits = [_hit(11)]
    monkeypatch.setattr(md.jamendo_music, "search_tracks",
                        lambda direction, client_id, limit=20: hits)
    monkeypatch.setattr(md.jamendo_music, "download_track",
                        lambda url, output_path: (Path(output_path).write_bytes(b"ID3x"), True)[1])
    client = _SeqClient([
        {"search_query": "cello", "energy": "low", "bpm_range": [50, 60],
         "instruments": [], "avoid": []},
        {"track_id": "999", "rationale": "not in list"},  # unknown -> heuristic
    ])
    out = md.select_music(client, _ctx(), "KEY", tmp_path)
    assert out is not None  # heuristic pick_from_pool chose the single hit


def test_select_music_malformed_hit_does_not_raise(tmp_path, monkeypatch):
    # Non-numeric duration makes pick_from_pool's `>= 15` raise TypeError;
    # select_music must swallow it and return None (never raises).
    bad = _hit(11)
    bad["duration"] = "lots"
    monkeypatch.setattr(md.jamendo_music, "search_tracks",
                        lambda direction, client_id, limit=20: [bad])
    client = _SeqClient([
        {"search_query": "cello", "energy": "low", "bpm_range": [50, 60],
         "instruments": [], "avoid": []},
        {"track_id": "999", "rationale": "not in list"},
    ])
    assert md.select_music(client, _ctx(), "KEY", tmp_path) is None
