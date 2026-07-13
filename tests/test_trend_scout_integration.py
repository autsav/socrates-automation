import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline
from studio.types import TrendHook


class _Cfg:
    GNEWS_API_KEY = "K"
    ANTHROPIC_API_KEY = "A"


def test_apply_trend_scout_sets_hook_and_bridge(monkeypatch):
    monkeypatch.setattr(pipeline, "_trend_fetch", lambda cfg: [{"topic": "AI layoffs", "source": "gnews"}])
    monkeypatch.setattr(pipeline, "_trend_pick",
                        lambda cfg, cands, qctx: TrendHook(used=True, topic="AI layoffs", source="gnews",
                                                           hook="AI is stealing your time.", bridge="But Socrates knew."))
    qd = pipeline._apply_trend_scout(_Cfg(), {"quote": "q", "mood": "dark_philosophical", "audience": "overwhelmed"})
    assert qd["hook"] == "AI is stealing your time."
    assert qd["bridge"] == "But Socrates knew."


def test_apply_trend_scout_unused_leaves_hook(monkeypatch):
    monkeypatch.setattr(pipeline, "_trend_fetch", lambda cfg: [{"topic": "x", "source": "gnews"}])
    monkeypatch.setattr(pipeline, "_trend_pick", lambda cfg, cands, qctx: TrendHook(used=False))
    qd = pipeline._apply_trend_scout(_Cfg(), {"quote": "q", "mood": "m"})
    assert "hook" not in qd or not qd.get("hook")
    assert not qd.get("bridge")


def test_apply_trend_scout_no_key_noop():
    class _C: GNEWS_API_KEY = ""; ANTHROPIC_API_KEY = "A"
    qd = pipeline._apply_trend_scout(_C(), {"quote": "q"})
    assert not qd.get("bridge")


def test_apply_trend_scout_skips_injected_bridge():
    qd = pipeline._apply_trend_scout(_Cfg(), {"quote": "q", "bridge": "already here"})
    assert qd["bridge"] == "already here"  # injected content not overridden
