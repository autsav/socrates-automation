"""Phases D+E: caption SEO/gap, recency weighting, first comment."""
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline
from src.content import trend_sources as ts
from src.engagement.first_comment import post_comment, first_comment_text


def test_caption_gap_trims_long_first_line():
    cap = "This is a very long first line that keeps going well past eight words\nBody."
    out = pipeline._enforce_caption_gap(cap)
    assert len(out.split("\n")[0].split()) <= 9   # 8 words + ellipsis marker
    assert out.split("\n")[0].endswith("…")


def test_caption_gap_uses_story_first_line():
    out = pipeline._enforce_caption_gap("Old first line here\nBody.", "He chose the barrel.")
    assert out.split("\n")[0] == "He chose the barrel."


def test_seo_line_per_audience():
    assert "procrastinat" in pipeline._seo_line("procrastinator")
    assert "stoic" in pipeline._seo_line("unknown-audience").lower()


def test_gnews_returns_tuples(monkeypatch):
    fake = Mock()
    fake.raise_for_status = lambda: None
    fake.json = lambda: {"articles": [{"title": "A", "publishedAt": "2026-07-19T10:00:00Z"},
                                      {"title": "B"}]}
    monkeypatch.setattr(ts.requests, "get", lambda *a, **k: fake)
    out = ts.gnews_headlines("KEY")
    assert out == [("A", "2026-07-19T10:00:00Z"), ("B", None)]


def test_fetch_trends_recency_first(monkeypatch):
    from datetime import datetime, timedelta, timezone
    fresh = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    stale = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()
    monkeypatch.setattr(ts, "google_trends", lambda n: [])
    monkeypatch.setattr(ts, "gnews_headlines",
                        lambda key, limit=10: [("Old story", stale), ("Fresh story", fresh)])

    class _Cfg:
        GNEWS_API_KEY = "k"
    out = ts.fetch_trends(_Cfg())
    topics = [c["topic"] for c in out]
    assert topics.index("Fresh story") < topics.index("Old story")


def test_post_comment_hits_graph(monkeypatch):
    calls = {}

    def fake_post(url, params=None, timeout=None):
        calls["url"] = url
        calls["message"] = params["message"]
        r = Mock(); r.status_code = 200
        return r
    import src.engagement.first_comment as fc
    monkeypatch.setattr(fc.requests, "post", fake_post)
    assert post_comment("MEDIA1", "Agree or disagree?", "EAAtok") is True
    assert "/MEDIA1/comments" in calls["url"]
    assert "graph.facebook.com" in calls["url"]     # EAA token routes to FB graph


def test_post_comment_never_raises(monkeypatch):
    import src.engagement.first_comment as fc
    monkeypatch.setattr(fc.requests, "post", Mock(side_effect=RuntimeError("down")))
    assert post_comment("M", "t", "EAAtok") is False


def test_first_comment_text_prefers_debate_cta():
    qd = {"arc": "story", "cta": "Discipline or talent — pick a side", "row_number": 1}
    assert first_comment_text(qd) == "Discipline or talent — pick a side"
    qd2 = {"arc": "classic", "cta": "Save this.", "row_number": 2}
    assert first_comment_text(qd2)                  # falls back to the pool
