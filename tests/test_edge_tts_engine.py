from pathlib import Path
from unittest.mock import patch

from src.audio.edge_tts_engine import (
    get_voice_for_mood,
    generate_scene_voiceover_edge_tts,
    prepare_reel_voiceover_edge_tts,
    parse_word_srt,
    edge_tts_available,
    VOICE_MAP,
    DEFAULT_VOICE,
)

SEAM = "src.audio.edge_tts_engine._edge_tts_synth"


def _fake_synth(words):
    """Build an async stand-in for _edge_tts_synth that writes an mp3 and
    returns the given per-word timings."""
    async def synth(text, voice, media_path):
        Path(media_path).write_bytes(b"fake-mp3-bytes")
        return list(words)
    return synth


def test_get_voice_for_mood_known():
    for mood, voice in VOICE_MAP.items():
        assert get_voice_for_mood(mood) == voice


def test_get_voice_for_mood_unknown_falls_back_to_default():
    assert get_voice_for_mood("nonexistent_mood") == DEFAULT_VOICE


def test_generate_scene_voiceover_edge_tts_success(tmp_path):
    output_path = tmp_path / "voice.mp3"
    words = [
        {"w": "Know", "start": 0.1, "end": 0.4},
        {"w": "thyself.", "start": 0.4, "end": 0.9},
    ]

    with patch(SEAM, side_effect=_fake_synth(words)):
        ok = generate_scene_voiceover_edge_tts("Know thyself.", "en-US-ChristopherNeural", output_path)

    assert ok is True
    assert output_path.exists()

    # A word-level SRT is written and round-trips to per-word timings.
    srt = output_path.with_suffix(".srt")
    assert srt.exists()
    parsed = parse_word_srt(srt)
    assert len(parsed) == 2
    assert parsed[0]["w"] == "Know"
    assert parsed[1]["w"] == "thyself."


def test_generate_scene_voiceover_edge_tts_failure(tmp_path):
    output_path = tmp_path / "voice.mp3"

    async def boom(text, voice, media_path):
        raise RuntimeError("tts error")

    with patch(SEAM, side_effect=boom):
        ok = generate_scene_voiceover_edge_tts("Know thyself.", "en-US-ChristopherNeural", output_path)

    assert ok is False
    assert not output_path.exists()


def test_generate_scene_voiceover_edge_tts_empty_audio_is_failure(tmp_path):
    output_path = tmp_path / "voice.mp3"

    async def empty(text, voice, media_path):
        Path(media_path).write_bytes(b"")  # no audio
        return []

    with patch(SEAM, side_effect=empty):
        ok = generate_scene_voiceover_edge_tts("Know thyself.", "en-US-ChristopherNeural", output_path)

    assert ok is False
    assert not output_path.exists()


def test_generate_scene_voiceover_edge_tts_trims_long_text(tmp_path):
    output_path = tmp_path / "voice.mp3"
    long_text = "a" * 500
    captured = {}

    async def synth(text, voice, media_path):
        captured["text"] = text
        Path(media_path).write_bytes(b"fake")
        return []

    with patch(SEAM, side_effect=synth):
        generate_scene_voiceover_edge_tts(long_text, "en-US-ChristopherNeural", output_path)

    assert len(captured["text"]) <= 300


def test_prepare_reel_voiceover_edge_tts_all_success(tmp_path):
    words = [{"w": "x", "start": 0.0, "end": 0.2}, {"w": "y", "start": 0.2, "end": 0.4}]

    with patch(SEAM, side_effect=_fake_synth(words)):
        result = prepare_reel_voiceover_edge_tts(
            hook_text="This will change everything.",
            quote_text="Know thyself.",
            cta_text="Follow for more.",
            mood="dark_philosophical",
            output_dir=tmp_path,
            timestamp="20260101",
        )

    assert result["voice"] == "en-US-ChristopherNeural"
    assert result["hook_voice"] is not None
    assert result["quote_voice"] is not None
    assert result["cta_voice"] is not None
    assert Path(result["hook_voice"]).exists()
    # Per-word timings propagate through to the caller.
    assert len(result["hook_words"]) == 2
    assert result["quote_words"][0]["w"] == "x"


def test_prepare_reel_voiceover_edge_tts_partial_failure(tmp_path):
    calls = {"n": 0}

    async def synth(text, voice, media_path):
        calls["n"] += 1
        if calls["n"] == 2:  # second scene (quote) fails
            raise RuntimeError("failed")
        Path(media_path).write_bytes(b"fake")
        return [{"w": "w", "start": 0.0, "end": 0.1}]

    with patch(SEAM, side_effect=synth):
        result = prepare_reel_voiceover_edge_tts(
            hook_text="hook", quote_text="quote", cta_text="cta",
            mood="calm_stoic", output_dir=tmp_path, timestamp="ts",
        )

    assert result["hook_voice"] is not None
    assert result["quote_voice"] is None
    assert result["cta_voice"] is not None
    assert result["quote_words"] == []


def test_edge_tts_available_true():
    # edge-tts is a declared dependency; importable -> available.
    assert edge_tts_available() is True


def test_edge_tts_available_false_when_missing():
    import sys
    with patch.dict(sys.modules, {"edge_tts": None}):
        assert edge_tts_available() is False
