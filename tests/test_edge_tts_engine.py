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
    async def synth(text, voice, media_path, rate="+0%", pitch="+0Hz"):
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

    async def boom(text, voice, media_path, rate="+0%", pitch="+0Hz"):
        raise RuntimeError("tts error")

    with patch(SEAM, side_effect=boom):
        ok = generate_scene_voiceover_edge_tts("Know thyself.", "en-US-ChristopherNeural", output_path)

    assert ok is False
    assert not output_path.exists()


def test_generate_scene_voiceover_edge_tts_empty_audio_is_failure(tmp_path):
    output_path = tmp_path / "voice.mp3"

    async def empty(text, voice, media_path, rate="+0%", pitch="+0Hz"):
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

    async def synth(text, voice, media_path, rate="+0%", pitch="+0Hz"):
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

    assert result["voice"] == "en-US-AndrewNeural"  # the sage reel voice
    assert result["hook_voice"] is not None
    assert result["quote_voice"] is not None
    assert result["cta_voice"] is not None
    assert Path(result["hook_voice"]).exists()
    # Per-word timings propagate through to the caller.
    assert len(result["hook_words"]) == 2
    assert result["quote_words"][0]["w"] == "x"


def test_prepare_reel_uses_sage_voice_and_prosody(tmp_path):
    from src.audio.edge_tts_engine import REEL_VOICE, REEL_RATE, REEL_PITCH
    seen = []

    async def synth(text, voice, media_path, rate="+0%", pitch="+0Hz"):
        seen.append((voice, rate, pitch))
        Path(media_path).write_bytes(b"fake")
        return []

    with patch(SEAM, side_effect=synth):
        prepare_reel_voiceover_edge_tts(
            hook_text="h", quote_text="q", cta_text="c",
            mood="epic_warrior",  # mood must NOT change the voice anymore
            output_dir=tmp_path, timestamp="ts",
        )

    # All three scenes use the fixed sage voice, each with its scene-arc prosody.
    from src.audio.edge_tts_engine import SCENE_PROSODY
    assert seen == [(REEL_VOICE, *SCENE_PROSODY["hook"]),
                    (REEL_VOICE, *SCENE_PROSODY["quote"]),
                    (REEL_VOICE, *SCENE_PROSODY["cta"])]


def test_prepare_reel_voiceover_edge_tts_partial_failure(tmp_path):
    calls = {"n": 0}

    async def synth(text, voice, media_path, rate="+0%", pitch="+0Hz"):
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


def test_scene_prosody_defines_all_four_scenes():
    from src.audio import edge_tts_engine as e
    assert set(e.SCENE_PROSODY) == {"hook", "bridge", "quote", "cta"}
    rates = {k: int(v[0].rstrip("%")) for k, v in e.SCENE_PROSODY.items()}
    # The quote is the payoff — it must be the slowest scene; the hook must
    # be the most energetic (least slowed).
    assert rates["quote"] < rates["bridge"] < rates["hook"]
    assert rates["quote"] < rates["cta"]


def test_prepare_uses_per_scene_prosody(monkeypatch, tmp_path):
    from src.audio import edge_tts_engine as e
    calls = {}

    def fake_scene(text, voice, path, rate, pitch):
        # key by filename segment (hook/quote/cta)
        for k in ("hook", "quote", "cta"):
            if k in str(path):
                calls[k] = (rate, pitch)
        return False   # skip srt handling

    monkeypatch.setattr(e, "generate_scene_voiceover_edge_tts", fake_scene)
    e.prepare_reel_voiceover_edge_tts("h", "q", "c", "dark_philosophical",
                                      str(tmp_path), "ts1")
    assert calls["hook"] == e.SCENE_PROSODY["hook"]
    assert calls["quote"] == e.SCENE_PROSODY["quote"]
    assert calls["cta"] == e.SCENE_PROSODY["cta"]
