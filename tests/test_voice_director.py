"""Directed delivery: per-scene ElevenLabs settings, chapter breaks, gravitas."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.audio.voice_director import (
    delivery_profile, insert_chapter_breaks, apply_gravitas)


def test_profiles_differ_by_scene():
    hook = delivery_profile("hook")
    quote = delivery_profile("quote")
    cta = delivery_profile("cta")
    # Hook is expressive (low stability, high style); quote is gravitas
    # (high stability, low style). They must not be the same read.
    assert hook["stability"] < quote["stability"]
    assert hook["style"] > quote["style"]
    assert isinstance(cta, dict)


def test_bridge_urgency_builds_across_chapters():
    early = delivery_profile("bridge", chapter_index=0)
    late = delivery_profile("bridge", chapter_index=4)
    assert late["stability"] < early["stability"]  # urgency rises


def test_unknown_scene_returns_empty_overrides():
    assert delivery_profile("nonsense") == {}


def test_chapter_breaks_inserted_between_sentence_groups():
    text = ("He walked into the storm. No shoes. His friends stared. "
            "He smiled back. Then he did it again the next day. Nobody laughed then.")
    out = insert_chapter_breaks(text)
    assert '<break time="0.4s" />' in out
    # Original words all survive.
    for w in ("storm", "friends", "smiled", "Nobody"):
        assert w in out


def test_apply_gravitas_returns_false_on_missing_file(tmp_path):
    assert apply_gravitas(tmp_path / "nope.mp3") is False


def test_apply_gravitas_skips_files_with_break_tags(tmp_path):
    """Files with sibling SRT containing <break> must NOT be pitch-down'd —
    pitch-shift warps the timing of inserted pauses."""
    from unittest.mock import patch
    from src.audio import voice_director

    mp3 = tmp_path / "voice.mp3"
    mp3.write_bytes(b"\x00")
    srt = tmp_path / "voice.srt"
    srt.write_text('1\n00:00:00,000 --> 00:00:01,000\nHello <break time="0.5s" /> world\n')

    with patch.object(voice_director.subprocess, "run") as mock_run:
        result = voice_director.apply_gravitas(mp3)

    assert result is False
    mock_run.assert_not_called()
