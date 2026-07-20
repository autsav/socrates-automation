"""Dramatic pools: human struggle, not scenery — the emotional charge the
winning accounts borrow from movie clips (spec 2)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.visual import stock_footage as sf
from src.content.trend_sources import is_unsafe


def test_pools_cover_all_moods_with_six_plus_safe_queries():
    for mood in sf.MOOD_SEARCH_TERMS:
        pool = sf.DRAMATIC_POOLS[mood]
        assert len(pool) >= 6, mood
        for q in pool:
            assert not is_unsafe(q), q
            assert not sf._is_scenery(q), q
            assert set(q.split()) & sf._HUMAN_WORDS, q


def test_scenery_heuristic():
    assert sf._is_scenery("beautiful sunset over ocean")
    assert sf._is_scenery("mountain landscape clouds")
    assert not sf._is_scenery("boxer wrapping hands dark gym")
    assert not sf._is_scenery("man walking into storm rain")


def test_fetch_reel_clips_dedupes_and_survives_failures(tmp_path, monkeypatch):
    calls = []

    def fake_search(mood, api_key, query=None):
        calls.append(query)
        return [{"id": 1, "video_files": []}] if len(calls) < 3 else [{"id": 2, "video_files": []}]

    monkeypatch.setattr(sf, "search_stock_video", fake_search)
    monkeypatch.setattr(sf, "pick_best_video", lambda v, **k: v[0])

    def fake_download(video, output_path):
        p = Path(output_path)
        p.write_bytes(b"x")
        return p

    monkeypatch.setattr(sf, "download_stock_video", fake_download)
    clips = sf.fetch_reel_clips("dark_philosophical", "key", tmp_path, n=4)
    assert 1 <= len(clips) <= 2          # id 1 deduped, id 2 distinct
    assert all(p.exists() for p in clips)


def test_fetch_reel_clips_total_failure_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(sf, "search_stock_video",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("api down")))
    assert sf.fetch_reel_clips("dark_philosophical", "key", tmp_path) == []
