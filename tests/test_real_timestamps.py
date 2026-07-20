"""Real word timings from ElevenLabs character alignment (spec 1).
The faked even-spread timings were the voice/text desync root cause."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.audio.elevenlabs_engine import _alignment_to_words, generate_voiceover


def _align(chars, starts, ends):
    return {"characters": chars, "character_start_times_seconds": starts,
            "character_end_times_seconds": ends}


def test_groups_characters_into_words():
    text = "He walked."
    chars = list("He walked.")
    starts = [0.0, 0.1, 0.2, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6]
    ends = [s + 0.05 for s in starts]
    words = _alignment_to_words(text, _align(chars, starts, ends))
    assert [w["w"] for w in words] == ["He", "walked."]
    assert words[0]["start"] == 0.0 and words[0]["end"] == 0.15
    assert words[1]["start"] == 0.3          # 'w' starts after the space
    assert words[1]["end"] == 0.65


def test_break_tags_excluded():
    text = 'One. <break time="0.4s" /> Two.'
    chars = list(text)
    starts = [round(i * 0.05, 2) for i in range(len(chars))]
    ends = [s + 0.04 for s in starts]
    words = _alignment_to_words(text, _align(chars, starts, ends))
    assert [w["w"] for w in words] == ["One.", "Two."]


def test_malformed_alignment_returns_empty():
    assert _alignment_to_words("hi", None) == []
    assert _alignment_to_words("hi", {}) == []
    assert _alignment_to_words("hi", {"characters": ["h"],
                                      "character_start_times_seconds": []}) == []


def test_falls_back_to_plain_endpoint_when_with_timestamps_unavailable(tmp_path, monkeypatch):
    """with-timestamps raises -> plain endpoint still produces the file, and
    last_words is [] so callers know to estimate instead of trusting stale data."""
    import requests
    from src.audio import elevenlabs_engine as el_engine

    calls = []

    class _FakeResponse:
        def __init__(self, content=b""):
            self.content = content

        def raise_for_status(self):
            pass

        def json(self):
            raise AssertionError("plain endpoint response should not be JSON-decoded")

    def _fake_post(url, headers=None, json=None, timeout=None):
        calls.append(url)
        if "with-timestamps" in url:
            raise el_engine.requests.exceptions.RequestException("boom")
        return _FakeResponse(content=b"fake-audio-bytes")

    monkeypatch.setattr(requests, "post", _fake_post)

    out_path = tmp_path / "vo.mp3"
    result = generate_voiceover("hi there", "fake-key", "intense", out_path)

    assert result == out_path
    assert out_path.read_bytes() == b"fake-audio-bytes"
    assert generate_voiceover.last_words == []
    assert any("with-timestamps" in u for u in calls)
    assert any("with-timestamps" not in u for u in calls)
