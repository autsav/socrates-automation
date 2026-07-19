"""Code replacement for the retired director agent (spec 1.4): rubric picks
the concept; the Decision shape is preserved so downstream is untouched."""
from src.core.excel_reader import AUDIENCE_TO_MOOD
from studio.rubric import score_concept
from studio.types import Decision


def pick_concept(concepts):
    """Highest rubric score wins; ties go to the earliest (stable)."""
    return max(concepts, key=lambda c: (score_concept(c.hook, c.caption),
                                        -concepts.index(c)))


def build_decision(concept, brief) -> Decision:
    mood = AUDIENCE_TO_MOOD.get(getattr(brief, "audience", ""),
                                "dark_philosophical")
    return Decision(scores=[], top_pick=concept.id, alt_pick=None,
                    revision={}, visual_direction={"mood": mood,
                                                   "flux_prompt": ""},
                    rationale="rubric pick (director retired)")
