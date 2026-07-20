"""7-15s punch arc: one brutal line -> quote -> send CTA (spec 4) + persona."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline
from studio.story_writer import validate_story, _PREFIX


def test_punch_mode_budgets():
    good = {"beat_hook": "Nobody is coming to save you, and you already know it.",
            "beat_reframe": "",
            "quote_row": 3,
            "beat_cta": "Send this to the friend who keeps waiting for someone else to fix it.",
            "topic_query": "man alone rooftop", "caption_first_line": "Read that again."}
    ok, r = validate_story(good, mode="punch")
    assert ok, r
    # Story mode still enforces the long-form floor.
    assert validate_story(good)[0] is False
    too_long = dict(good, beat_hook=" ".join(["word"] * 40),
                    beat_cta=" ".join(["word"] * 40))
    assert validate_story(too_long, mode="punch")[0] is False


def test_rotations_contain_punch_at_twenty_percent():
    for rot in (pipeline._ARC_ROTATION_TREND, pipeline._ARC_ROTATION_NO_TREND):
        assert rot.count("punch") == 2 and len(rot) == 10


def test_persona_in_prefix():
    assert "first person" in _PREFIX.lower() or '"I"' in _PREFIX


def test_signoff_appended_to_caption():
    cap = pipeline._append_signoff("Line one.\n#stoic")
    assert cap.rstrip().endswith("— The Stoic Reset") is False  # hashtags last
    assert "— The Stoic Reset" in cap
    # Idempotent: never doubled.
    assert pipeline._append_signoff(cap).count("— The Stoic Reset") == 1


def test_punch_beats_force_empty_reframe(monkeypatch):
    import pipeline as p

    def fake_write_story(client, mode, material, pool, extra_context=""):
        return {"beat_hook": "Nobody is coming to rescue you from this couch tonight.",
                "beat_reframe": "Rogue reframe the model should not have written here.",
                "quote_row": 1,
                "beat_cta": "Send this to the friend who keeps waiting for someday to arrive.",
                "topic_query": "man alone rooftop", "caption_first_line": "Read it twice."}

    monkeypatch.setattr("studio.story_writer.write_story", fake_write_story)

    class _Cfg:
        ANTHROPIC_API_KEY = "k"

    story = p._build_story_beats(_Cfg(), "punch", {"row_number": 1, "quote": "q", "audience": "stuck"})
    assert story is not None and story["beat_reframe"] == ""
