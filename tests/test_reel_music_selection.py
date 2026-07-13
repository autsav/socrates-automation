import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline


class _Cfg:
    JAMENDO_CLIENT_ID = ""
    ANTHROPIC_API_KEY = "A"


def test_falls_back_to_mood_music_without_jamendo_key(monkeypatch):
    # No Jamendo key -> music director must NOT be invoked; mood path used.
    called = {"director": False, "mood": False}

    def fake_director(*a, **k):
        called["director"] = True
        return None

    def fake_mood(mood, output_dir=""):
        called["mood"] = True
        return Path("/tmp/mood.mp3")

    monkeypatch.setattr(pipeline.music_director, "select_music", fake_director)
    monkeypatch.setattr(pipeline, "download_music_for_mood", fake_mood, raising=False)

    out = pipeline._select_reel_music(_Cfg(), {"quote": "q"}, "hook", "dark_philosophical")
    assert out == Path("/tmp/mood.mp3")
    assert called["director"] is False
    assert called["mood"] is True


def test_uses_music_director_when_keys_present(monkeypatch):
    class _Cfg2:
        JAMENDO_CLIENT_ID = "P"
        ANTHROPIC_API_KEY = "A"

    monkeypatch.setattr(pipeline, "StudioClient",
                        lambda key: type("C", (), {"over_daily_ceiling": lambda self: False})())
    monkeypatch.setattr(pipeline.music_director, "select_music",
                        lambda client, ctx, key, out: Path("/tmp/director.mp3"))
    out = pipeline._select_reel_music(_Cfg2(), {"quote": "q"}, "hook", "dark_philosophical")
    assert out == Path("/tmp/director.mp3")
