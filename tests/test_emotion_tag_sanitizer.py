"""Tests for src/audio/emotion_tags.py."""
from src.audio.emotion_tags import (
    EMOTION_TAGS, sanitize_for_tts, expand_chapter_breaks,
)


def test_known_emotion_tags_constant():
    expected = {"[sighs]", "[dryly]", "[sarcastically]", "[emphatic]", "[calmly]", "[pause]"}
    assert EMOTION_TAGS == expected


def test_pause_tag_becomes_break():
    text = "First sentence.[pause] Second sentence."
    out = sanitize_for_tts(text)
    assert '<break time="0.5s" />' in out
    assert "[pause]" not in out


def test_other_tags_preserved():
    text = "[calmly]Hello there.[emphatic]Listen."
    out = sanitize_for_tts(text)
    assert "[calmly]" in out
    assert "[emphatic]" in out


def test_chapter_breaks_collapse_consecutive_pauses():
    text = "A.[pause] B.[pause] C."
    out = expand_chapter_breaks(text)
    # No two breaks adjacent
    assert "><break" not in out  # malformed adjacency check
    assert out.count("<break") == 2
