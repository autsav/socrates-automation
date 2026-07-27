"""Tests for ElevenLabs voice roster (baritones)."""
from src.audio import elevenlabs_engine


def test_baritone_voices_present():
    assert "josh" in elevenlabs_engine.VOICES
    assert "bill" in elevenlabs_engine.VOICES
    assert "david" in elevenlabs_engine.VOICES
    for key in ("josh", "bill", "david"):
        assert elevenlabs_engine.VOICES[key], f"VOICES[{key}] is empty"


def test_reel_voice_is_bill():
    assert elevenlabs_engine.REEL_VOICE == "bill"


def test_mood_voices_route_to_baritones():
    assert elevenlabs_engine.MOOD_VOICES["dark_philosophical"] == "bill"
    assert elevenlabs_engine.MOOD_VOICES["cinematic_hopeful"] == "david"
    assert elevenlabs_engine.MOOD_VOICES["epic_warrior"] in {"bill", "josh"}