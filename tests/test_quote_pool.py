"""The writer picks the quote; the chosen row becomes the consumed row (spec 2)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline


def test_quote_pool_today_first_and_capped(monkeypatch):
    rows = [{"row_number": i, "quote": f"q{i}", "audience": "stuck"} for i in range(30)]
    monkeypatch.setattr("studio.run._build_pool", lambda p: rows)
    pool = pipeline._quote_pool({"row_number": 7, "quote": "q7"})
    assert pool[0]["row_number"] == 7
    assert len(pool) <= 20
    assert all("quote" in e and "row_number" in e for e in pool)


def test_quote_pool_failure_falls_back(monkeypatch):
    monkeypatch.setattr("studio.run._build_pool",
                        lambda p: (_ for _ in ()).throw(RuntimeError("no excel")))
    pool = pipeline._quote_pool({"row_number": 3, "quote": "today"})
    assert pool == [{"row_number": 3, "quote": "today",
                     "attribution": pool[0].get("attribution", "— Socrates")}] or \
           (len(pool) == 1 and pool[0]["row_number"] == 3)


def test_chosen_row_swaps_into_quote_data(monkeypatch):
    def fake_write_story(client, mode, material, pool, extra_context=""):
        return {"beat_hook": "You keep score of everything you could lose tomorrow night.",
                "beat_reframe": ("You count it quietly. " + "He kept walking. " * 60
                                 + "And nobody expected what he did next. "
                                 + "He kept walking. " * 10),
                "quote_row": 12, "beat_cta": "Send this to the friend who would start over.",
                "topic_query": "man storm", "caption_first_line": "He lost it all."}

    monkeypatch.setattr("studio.story_writer.write_story", fake_write_story)
    monkeypatch.setattr(pipeline, "_quote_pool", lambda qd: [
        {"row_number": 5, "quote": "today quote", "attribution": "— A"},
        {"row_number": 12, "quote": "chosen quote", "attribution": "— B"}])

    class _Cfg:
        ANTHROPIC_API_KEY = "k"

    qd = {"row_number": 5, "quote": "today quote", "audience": "stuck"}
    story = pipeline._build_story_beats(_Cfg(), "weird", qd)
    assert story is not None
    assert qd["row_number"] == 12 and qd["quote"] == "chosen quote"
    assert qd["attribution"] == "— B"
