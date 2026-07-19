"""Director retired (spec 1.4): code picks the concept, deterministically."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio.concept_picker import pick_concept, build_decision
from studio.types import Concept


def _concept(cid, hook, caption="First line.\nBody text here."):
    return Concept(id=cid, angle_label="a", hook=hook, caption=caption,
                   cta="save this", reel_scenes=[], hashtags=[])


class _Brief:
    audience = "stuck"
    quote = {"row_number": 1, "text": "q"}

    def to_dict(self):
        return {}


def test_concrete_statement_concept_wins():
    c = pick_concept([
        _concept("a", "Is success just mindset?"),
        _concept("b", "He threw away his only cup."),
    ])
    assert c.id == "b"


def test_tie_goes_to_first():
    c = pick_concept([_concept("a", "Same hook."), _concept("b", "Same hook.")])
    assert c.id == "a"


def test_build_decision_shape():
    d = build_decision(_concept("a", "Hook."), _Brief())
    assert d.top_pick == "a"
    assert d.visual_direction["mood"]
    assert d.revision == {}
