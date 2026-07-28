"""Tests for src.mpt_adapter — SRT → word_timings.json translator.

MPT CLI always emits SRT (never JSON timings). Task 3 produces the
word_timings.json schema consumed by HyperFrames overlay renderer.

Spec schema:
  {"scenes": {"hook": {"words": [{"t": float, "w": str}], "duration_sec": float, "start_sec": float},
              "bridge": {...}, "quote": {...}, "cta": {...}},
   "total_duration_sec": float}
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mpt_adapter import srt_to_word_timings


def test_srt_basic_one_scene():
    srt = """1
00:00:00,420 --> 00:00:02,500
The unexamined life

2
00:00:02,500 --> 00:00:04,800
is not worth living
"""
    result = srt_to_word_timings(srt)
    assert "scenes" in result
    assert "total_duration_sec" in result
    # MPT emits one continuous SRT → all 4 scenes populated (start_sec differs)
    assert all(s in result["scenes"] for s in ("hook", "bridge", "quote", "cta"))
    # First scene has all words (we don't split mid-SRT — consumers slice)
    hook_words = result["scenes"]["hook"]["words"]
    assert hook_words[0] == {"t": 0.42, "w": "The"}
    assert hook_words[-1] == {"t": 2.5, "w": "living"}
    assert result["scenes"]["hook"]["duration_sec"] == 4.8
    assert result["total_duration_sec"] == 4.8


def test_srt_handles_empty():
    result = srt_to_word_timings("")
    assert result["scenes"]["hook"]["words"] == []
    assert result["total_duration_sec"] == 0.0


def test_srt_handles_long_timestamps():
    srt = """1
00:01:30,000 --> 00:01:32,500
Hello world
"""
    result = srt_to_word_timings(srt)
    assert result["scenes"]["hook"]["words"][0]["t"] == 90.0
    assert result["total_duration_sec"] == 92.5
