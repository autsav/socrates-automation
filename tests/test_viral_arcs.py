"""Phase B: availability-aware rotation, beat mapping, fallbacks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline


def test_rotation_with_trend_is_story_heavy():
    arcs = [pipeline._pick_arc(i, has_trend=True) for i in range(10)]
    assert arcs.count("story") == 4
    assert arcs.count("weird") == 2
    assert pipeline._pick_arc(3, True) == pipeline._pick_arc(3, True)


def test_rotation_without_trend_mixes_weird_and_debate_story():
    arcs = [pipeline._pick_arc(i, has_trend=False) for i in range(10)]
    assert arcs.count("weird") == 3
    assert arcs.count("story") == 2          # debate-fed
    assert arcs.count("classic") + arcs.count("question") + arcs.count("cold_open") == 5


def test_fallback_arc_never_story():
    for i in range(8):
        assert pipeline._fallback_arc(i) in ("classic", "question", "cold_open")


def test_build_story_beats_weird_mode(monkeypatch):
    captured = {}

    def fake_write(client, mode, material, pool, extra_context=""):
        captured.update(mode=mode, material=material)
        return {"beat_hook": "A man lived in a barrel and won.",
                "beat_reframe": "He owned one cup, then threw it away.",
                "quote_row": 5, "beat_cta": "Send this to your freest friend.",
                "topic_query": "ancient greek ruins",
                "caption_first_line": "He chose the barrel.", "trend_tag": "stoicism"}
    monkeypatch.setattr("studio.story_writer.write_story", fake_write)
    monkeypatch.setattr("studio.client.StudioClient", lambda *a, **k: object())

    class _Cfg:
        ANTHROPIC_API_KEY = "k"
    out = pipeline._build_story_beats(_Cfg(), "weird", {"row_number": 5, "quote": "Q"})
    assert out["mode"] == "weird"
    assert captured["mode"] == "weird"
    assert "hook_fact" in captured["material"]          # weird capsule fed as material


def test_build_story_beats_debate_when_no_trend(monkeypatch):
    captured = {}

    def fake_write(client, mode, material, pool, extra_context=""):
        captured.update(mode=mode, material=material)
        return {"beat_hook": "Talent is an excuse.", "beat_reframe": "Reframe here.",
                "quote_row": 1, "beat_cta": "Pick a side in the comments.",
                "topic_query": "city night", "caption_first_line": "Choose.", "trend_tag": ""}
    monkeypatch.setattr("studio.story_writer.write_story", fake_write)
    monkeypatch.setattr("studio.client.StudioClient", lambda *a, **k: object())

    class _Cfg:
        ANTHROPIC_API_KEY = "k"
    out = pipeline._build_story_beats(_Cfg(), "story", {"row_number": 1, "quote": "Q"})
    assert captured["mode"] == "debate"
    assert "stance_seed" in captured["material"]


def test_build_story_beats_safety_fallback(monkeypatch):
    def unsafe_write(client, mode, material, pool):
        return {"beat_hook": "Taylor Swift ruined music forever.",
                "beat_reframe": "r", "quote_row": 1, "beat_cta": "c",
                "topic_query": "t", "caption_first_line": "f", "trend_tag": ""}
    monkeypatch.setattr("studio.story_writer.write_story", unsafe_write)
    monkeypatch.setattr("studio.client.StudioClient", lambda *a, **k: object())

    class _Cfg:
        ANTHROPIC_API_KEY = "k"
    assert pipeline._build_story_beats(_Cfg(), "weird", {"row_number": 2, "quote": "Q"}) is None


def test_build_story_beats_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("api down")
    monkeypatch.setattr("studio.story_writer.write_story", boom)

    class _Cfg:
        ANTHROPIC_API_KEY = "k"
    assert pipeline._build_story_beats(_Cfg(), "story", {"row_number": 2}) is None


def test_story_bridge_bypasses_pivot_trim():
    # Regression: _enforce_bridge_len cuts at the FIRST sentence end past the
    # cap, which collapsed a 190-word story to "Meet Cato." (12.8s reel).
    story = "Meet Cato. " + " ".join(["word"] * 180) + "."
    assert pipeline._bridge_for_vo({"bridge": story, "arc": "story"}) == story
    assert pipeline._bridge_for_vo({"bridge": story, "arc": "weird"}) == story
    trimmed = pipeline._bridge_for_vo({"bridge": story, "arc": "classic"})
    assert trimmed == "Meet Cato."  # pivot arcs keep the one-sentence cap
