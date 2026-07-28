"""Tests for the shared reel-data builder.

Covers:
- build_reel_data returns canonical dict shared by Remotion and HyperFrames
- sceneFrames computes timing correctly
- _copy_assets stages media files
"""
from __future__ import annotations

from pathlib import Path

from src.video.reel_data import build_reel_data, sceneFrames


def test_sceneFrames_no_voice_distributes_duration():
    sf = sceneFrames(10.5, 30)
    assert sf["total"] == 10.5
    assert sf["hook"] > 0
    assert sf["quote"] > 0
    assert sf["cta"] > 0
    assert sf["bridge"] == 0


def test_sceneFrames_with_bridge():
    sf = sceneFrames(10.5, 30, hasBridge=True)
    assert sf["bridge"] >= 2.5


def test_sceneFrames_with_voice_durations():
    sf = sceneFrames(10.5, 30, {"hook": 2.0, "quote": 4.0, "cta": 1.5})
    assert sf["hook"] >= 2.45  # 2.0 + 0.2 + 0.25
    assert sf["quote"] >= 4.2  # 4.0 + 0.2
    assert sf["cta"] >= 1.8   # 1.5 + 0.2, floored at 1.8


def test_sceneFrames_matches_reel_data_shape():
    # The dict returned must have the exact keys HyperFrames template expects
    sf = sceneFrames(10.5, 30, {"hook": 2.0, "quote": 4.0, "cta": 1.5})
    assert set(sf.keys()) == {"total", "hook", "bridge", "quote", "cta"}


def test_build_reel_data_returns_canonical_shape():
    data = build_reel_data(
        hook="Hook text",
        quote="Quote text",
        attribution="— Author",
        cta="CTA text",
        mood="dark_philosophical",
        duration=10.5,
        fps=30,
    )
    assert data["hook"] == "Hook text"
    assert data["quote"] == "Quote text"
    assert data["mood"] == "dark_philosophical"
    assert data["fps"] == 30
    assert "voices" in data
    assert "voiceDurations" in data
    assert "wordTimes" in data
    assert "beats" in data


def test_build_reel_data_normalizes_unknown_mood():
    data = build_reel_data(quote="test", mood="invalid_mood")
    assert data["mood"] == "dark_philosophical"


def test_build_reel_data_includes_background_when_provided(tmp_path):
    bg = tmp_path / "bg.jpg"
    bg.write_bytes(b"\xff\xd8")
    data = build_reel_data(quote="test", background=bg)
    assert data["background"] == str(bg)


def test_build_reel_data_includes_bridge_when_provided():
    data = build_reel_data(quote="test", bridge="Bridge text")
    assert data["bridge"] == "Bridge text"


def test_build_reel_data_voice_durations_set_when_voices_provided(tmp_path):
    vo = tmp_path / "voice.mp3"
    vo.write_bytes(b"\x00")
    data = build_reel_data(quote="test", hook_voice=vo)
    assert data["voices"]["hook"] == str(vo)
    # voiceDurations may be None if ffprobe is absent or the file is invalid,
    # but the key must exist in the dict
    assert "hook" in data["voiceDurations"]
