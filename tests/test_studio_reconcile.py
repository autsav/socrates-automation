import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio import reconcile


class _Resp:
    def __init__(self, data):
        self._d = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


def test_match_by_caption_substring():
    media = [{"id": "IG_1", "caption": "You already know what to do. #Stoicism",
              "timestamp": "t"}]
    assert reconcile.match({"caption_marker": "You already know what to do."}, media) == "IG_1"


def test_match_returns_none_when_absent():
    media = [{"id": "IG_1", "caption": "different", "timestamp": "t"}]
    assert reconcile.match({"caption_marker": "no overlap here"}, media) is None


def test_match_empty_marker_is_none():
    media = [{"id": "IG_1", "caption": "anything", "timestamp": "t"}]
    assert reconcile.match({"caption_marker": ""}, media) is None


def test_fetch_recent_media_parses():
    def getter(url, params=None, timeout=0):
        return _Resp({"data": [{"id": "IG_1", "caption": "c", "timestamp": "t"}]})
    out = reconcile.fetch_recent_media("tok", "ig", getter=getter)
    assert out == [{"id": "IG_1", "caption": "c", "timestamp": "t"}]


def test_reconcile_pending_backfills(tmp_path, monkeypatch):
    from src.core import data_store
    data_store.DB_PATH = tmp_path / "pipeline.db"
    data_store.init_db()
    decision_json = '{"visual_direction": {"caption_marker": "Stop waiting."}}'
    data_store.save_proposal(0, 3, "stuck", "reel", decision_json)

    def getter(url, params=None, timeout=0):
        return _Resp({"data": [{"id": "IG_9", "caption": "Stop waiting. Act now.",
                                "timestamp": "t"}]})
    n = reconcile.reconcile_pending("tok", "ig", getter=getter)
    assert n == 1
    assert data_store.get_pending_proposals() == []
