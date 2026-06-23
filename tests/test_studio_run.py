import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio import run
from studio.client import StudioError
from studio.types import PerformanceBrief, CreativeBrief, Decision, Concept


def _perf():
    return PerformanceBrief("2026-06-23T00:00:00", 5, 90, headline="h")


def _brief():
    return CreativeBrief("stuck", "fear", {"row_number": 3}, "reel", "a", [], [], 0, "x")


def _decision():
    return Decision([{"concept_id": "c1", "score": 9, "critique": "good"}],
                    "c1", None, {"requested": False, "concept_id": "", "feedback": ""},
                    {"mood": "epic_warrior", "flux_prompt": "x", "typography": "b",
                     "palette": "amber"}, "c1 wins")


class _OkClient:
    def over_daily_ceiling(self):
        return False


def test_run_studio_happy(monkeypatch):
    monkeypatch.setattr(run.analyst, "get_or_build_brief", lambda c: _perf())
    monkeypatch.setattr(run.strategist, "make_brief", lambda *a, **k: _brief())
    monkeypatch.setattr(run.copywriter, "draft",
                        lambda *a, **k: [Concept("c1", "a", "h", "c", "s", [], [])])
    monkeypatch.setattr(run.director, "review", lambda *a, **k: _decision())
    out = run.run_studio(_OkClient(), 0, [{"row_number": 3, "quote": "q"}], [])
    assert out is not None
    brief, decision, cmap = out
    assert decision.top_pick == "c1"
    assert cmap[decision.top_pick].id == "c1"


def test_run_studio_fallback_on_error(monkeypatch):
    monkeypatch.setattr(run.analyst, "get_or_build_brief",
                        lambda c: (_ for _ in ()).throw(StudioError("boom")))
    assert run.run_studio(_OkClient(), 0, [], []) is None


def test_run_studio_fallback_on_ceiling():
    class _Over:
        def over_daily_ceiling(self):
            return True
    assert run.run_studio(_Over(), 0, [], []) is None
