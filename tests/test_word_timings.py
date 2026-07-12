import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.audio import edge_tts_engine as e


def test_parse_word_srt(tmp_path):
    srt = tmp_path / "v.srt"
    srt.write_text(
        "1\n00:00:00,100 --> 00:00:00,500\nThe\n\n"
        "2\n00:00:00,500 --> 00:00:01,000\nunexamined\n\n",
        encoding="utf-8",
    )
    words = e.parse_word_srt(srt)
    assert words == [
        {"w": "The", "start": 0.1, "end": 0.5},
        {"w": "unexamined", "start": 0.5, "end": 1.0},
    ]


def test_parse_word_srt_missing_returns_empty(tmp_path):
    assert e.parse_word_srt(tmp_path / "nope.srt") == []
