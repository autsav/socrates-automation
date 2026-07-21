"""Subscores power the revision stage; score_hook powers the hook pass."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio.rubric import score_story_detailed, score_hook, score_story


def _story(hook, reframe, cta):
    return {"beat_hook": hook, "beat_reframe": reframe, "beat_cta": cta}


STRONG = _story("He ate stale bread on a marble floor for 3 days.",
                "Short. Sharp. It got worse. Then worse again. Nobody laughed.",
                "Send this to the friend who guards their stuff.")
WEAK_HOOK = _story("Success is really about mindset and growth.",
                   "Short. Sharp. It got worse. Then worse again. Nobody laughed.",
                   "Send this to the friend who guards their stuff.")


def test_subscores_in_range_and_keys():
    d = score_story_detailed(STRONG)
    for k in ("hook", "escalation", "cta", "simplicity"):
        assert 0.0 <= d[k] <= 10.0, k
    assert isinstance(d["total"], float) and isinstance(d["weaknesses"], list)


def test_weak_hook_gets_weakness_string():
    d = score_story_detailed(WEAK_HOOK)
    assert d["hook"] <= 4
    assert "hook lacks a concrete image or number" in d["weaknesses"]
    assert score_story_detailed(STRONG)["weaknesses"] == [] or \
        "hook lacks" not in " ".join(score_story_detailed(STRONG)["weaknesses"])


def test_total_orders_like_score_story():
    assert (score_story_detailed(STRONG)["total"] > score_story_detailed(WEAK_HOOK)["total"]) == \
           (score_story(STRONG) > score_story(WEAK_HOOK))


def test_garbage_never_raises():
    d = score_story_detailed({})
    assert d["total"] == 0.0 and d["weaknesses"] == []


def test_score_hook_ordering():
    concrete = "You checked your bank app 9 times before lunch."
    abstract = "Your mindset determines your success and growth."
    assert score_hook(concrete) > score_hook(abstract)
    assert score_hook("") >= 0.0
