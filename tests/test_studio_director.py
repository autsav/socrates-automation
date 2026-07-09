import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio import director
from studio.types import PerformanceBrief, CreativeBrief, Concept, Decision
from src.core.excel_reader import VALID_MOODS


def _perf():
    return PerformanceBrief("2026-06-23T00:00:00", 5, 90, headline="h")


def _brief():
    return CreativeBrief("stuck", "fear", {"row_number": 3, "text": "Know thyself"},
                         "reel", "confront", [], [], 0, "fear lands")


def _concepts():
    return [Concept("c1", "a", "h1", "cap", "save", ["s"], ["#x"]),
            Concept("c2", "b", "h2", "cap", "save", ["s"], ["#x"])]


def _decision(revise=False):
    return {"scores": [{"concept_id": "c1", "score": 8, "critique": "ok"}],
            "top_pick": "c1", "alt_pick": "c2",
            "revision": {"requested": revise, "concept_id": "c1",
                         "feedback": "punchier" if revise else ""},
            "visual_direction": {"mood": "epic_warrior", "flux_prompt": "x",
                                 "typography": "bold", "palette": "amber"},
            "rationale": "c1 is strongest"}


class _SeqClient:
    """Returns queued payloads in order; records role per call."""
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.roles = []

    def call(self, role, *a, **k):
        self.roles.append(role)
        return self.payloads.pop(0)


def test_review_no_revision():
    c = _SeqClient([_decision(revise=False)])
    d = director.review(c, _perf(), _brief(), _concepts())
    assert isinstance(d, Decision) and d.top_pick == "c1"
    assert d.visual_direction["mood"] in VALID_MOODS
    assert c.roles == ["director"]


def test_review_runs_one_revision_then_rescores():
    revised_concept = {"id": "c1", "angle_label": "a", "hook": "H!", "caption": "cap",
                       "cta": "save", "reel_scenes": ["s"], "hashtags": ["#x"]}
    c = _SeqClient([_decision(revise=True), revised_concept, _decision(revise=False)])
    d = director.review(c, _perf(), _brief(), _concepts())
    assert d.revision["requested"] is False
    assert c.roles == ["director", "copywriter", "director"]
