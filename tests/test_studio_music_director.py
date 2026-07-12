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
