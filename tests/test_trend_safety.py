import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.content import trend_sources as ts
import pipeline
from studio.types import TrendHook


# ── is_unsafe ────────────────────────────────────────────────────────────────

def test_is_unsafe_flags_unsafe_topics():
    for t in ["3 killed in shooting", "War in Ukraine escalates",
              "President wins election", "Deadly earthquake hits", "CEO arrested for fraud",
              "Cancer breakthrough", "Missile strike overnight"]:
        assert ts.is_unsafe(t), f"should flag: {t!r}"


def test_is_unsafe_passes_safe_and_avoids_word_boundary_false_positives():
    for t in ["AI burnout is surging", "Warrior mindset trends", "Warm weather returns",
              "Rewarding habits", "Productivity hacks", "Stoicism goes viral", "Elon Musk's new AI"]:
        assert not ts.is_unsafe(t), f"should NOT flag: {t!r}"


def test_is_unsafe_handles_empty_and_none():
    assert ts.is_unsafe("") is False
    assert ts.is_unsafe(None) is False


# ── fetch_trends filters unsafe candidates ───────────────────────────────────

def test_fetch_trends_drops_unsafe_candidates(monkeypatch):
    monkeypatch.setattr(ts, "google_trends", lambda limit=15: ["AI layoffs", "Deadly wildfire spreads"])
    monkeypatch.setattr(ts, "gnews_headlines", lambda key, limit=10: ["Burnout culture", "War crimes trial"])

    class _Cfg:
        GNEWS_API_KEY = "K"

    topics = [c["topic"] for c in ts.fetch_trends(_Cfg())]
    assert "AI layoffs" in topics and "Burnout culture" in topics
    assert "Deadly wildfire spreads" not in topics  # unsafe filtered
    assert "War crimes trial" not in topics          # unsafe filtered


# ── _apply_trend_scout post-filter (defense-in-depth) ────────────────────────

class _Cfg:
    GNEWS_API_KEY = "K"
    ANTHROPIC_API_KEY = "A"


def test_apply_trend_scout_rejects_unsafe_returned_hook(monkeypatch):
    # The agent slips through an unsafe hook; the deterministic post-filter must
    # discard it and leave the reel on the evergreen hook.
    monkeypatch.setattr(pipeline, "_trend_fetch", lambda cfg: [{"topic": "AI", "source": "gnews"}])
    monkeypatch.setattr(pipeline, "_trend_pick",
                        lambda cfg, cands, qctx: TrendHook(used=True, topic="AI",
                                                           hook="This shooting proves you're wasting your life.",
                                                           bridge="But Socrates knew."))
    qd = pipeline._apply_trend_scout(_Cfg(), {"quote": "q", "mood": "dark_philosophical"})
    assert not qd.get("bridge")       # unsafe hook rejected -> no bridge
    assert not qd.get("hook")         # evergreen -> hook untouched


def test_apply_trend_scout_keeps_safe_returned_hook(monkeypatch):
    monkeypatch.setattr(pipeline, "_trend_fetch", lambda cfg: [{"topic": "AI", "source": "gnews"}])
    monkeypatch.setattr(pipeline, "_trend_pick",
                        lambda cfg, cands, qctx: TrendHook(used=True, topic="AI burnout",
                                                           hook="AI is quietly stealing your time.",
                                                           bridge="But Socrates knew."))
    qd = pipeline._apply_trend_scout(_Cfg(), {"quote": "q", "mood": "dark_philosophical"})
    assert qd["hook"] == "AI is quietly stealing your time."
    assert qd["bridge"] == "But Socrates knew."
