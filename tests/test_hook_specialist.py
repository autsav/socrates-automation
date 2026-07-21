"""8-angle hook pass: coded validation + scoring, fallback-safe (spec 4)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio.hook_specialist import HOOK_ANGLES, generate_hooks, pick_hook


def test_eight_angles():
    assert len(HOOK_ANGLES) == 8 and len(set(HOOK_ANGLES)) == 8


def test_generate_hooks_calls_role(monkeypatch):
    class C:
        def call(self, role, prefix, role_system, user, schema):
            assert role == "hook_specialist"
            return {"hooks": [f"You feel angle {a} tonight." for a in HOOK_ANGLES]}
    hooks = generate_hooks(C(), {"beat_reframe": "story text", "beat_hook": "old"})
    assert len(hooks) == 8


def test_generate_hooks_failure_returns_empty():
    class Dead:
        def call(self, *a, **k):
            raise RuntimeError("api down")
    assert generate_hooks(Dead(), {}) == []


def test_pick_hook_validates_and_scores():
    cands = [
        "The lesson is that success comes from mindset.",   # no viewer + resolution
        "Why do you keep doing this?",                       # question
        "You checked your bank app 9 times before lunch.",   # concrete winner
        "Your mindset determines your growth and success.",  # abstract
    ]
    assert pick_hook(cands, "fallback you keep.") == \
        "You checked your bank app 9 times before lunch."


def test_pick_hook_all_invalid_falls_back():
    assert pick_hook(["No viewer here at all."], "You still matter tonight.") == \
        "You still matter tonight."


def test_resolution_set_matches_formula_gate():
    from studio.rubric import RESOLUTION_PHRASES
    assert "this means" in RESOLUTION_PHRASES and "the secret is" in RESOLUTION_PHRASES
    from studio.hook_specialist import pick_hook
    assert pick_hook(["You think this means you are safe now."],
                     "You still matter tonight.") == "You still matter tonight."
