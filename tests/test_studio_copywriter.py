import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio import copywriter
from studio.types import PerformanceBrief, CreativeBrief, Concept


def _perf():
    return PerformanceBrief("2026-06-23T00:00:00", 5, 90, headline="h")


def _brief():
    return CreativeBrief("stuck", "fear", {"row_number": 3, "text": "Know thyself"},
                         "reel", "confront", [], [], 0, "fear lands")


def _concept(i="c1"):
    return {"id": i, "angle_label": "a", "hook": "h", "caption": "c", "cta": "save",
            "reel_scenes": ["s"], "hashtags": ["#x"]}


class _FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.role = None

    def call(self, role, *a, **k):
        self.role = role
        return self.payload


def test_draft_returns_n_concepts():
    c = _FakeClient({"concepts": [_concept("c1"), _concept("c2")]})
    out = copywriter.draft(c, _perf(), _brief(), n=2)
    assert len(out) == 2 and all(isinstance(x, Concept) for x in out)
    assert c.role == "copywriter"


def test_revise_returns_single_concept():
    c = _FakeClient(_concept("c1"))
    out = copywriter.revise(c, _perf(), _brief(), Concept(**_concept()), "punchier hook")
    assert isinstance(out, Concept) and out.id == "c1"
