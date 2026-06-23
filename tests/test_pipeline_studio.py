import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline
from studio.types import CreativeBrief, Decision, Concept


def test_apply_studio_decision_maps_fields():
    """_apply_studio_decision turns a Decision into the quote_data dict the
    renderer consumes (caption, mood, hook, flux_prompt, caption_marker)."""
    brief = CreativeBrief("stuck", "fear", {"row_number": 7, "text": "Know thyself"},
                          "reel", "confront", [], [], 0, "x")
    decision = Decision(
        [{"concept_id": "c1", "score": 9, "critique": "ok"}], "c1", None,
        {"requested": False, "concept_id": "", "feedback": ""},
        {"mood": "epic_warrior", "flux_prompt": "FLUX", "typography": "b", "palette": "amber"},
        "rationale")
    concepts = {"c1": Concept("c1", "a", "You already know.", "CAPTION", "Save this.",
                              ["You already know.", "Know thyself", "Save this."], ["#Stoicism"])}
    qd = pipeline._apply_studio_decision(brief, decision, concepts)
    assert qd["quote"] == "Know thyself"
    assert qd["caption"] == "CAPTION"
    assert qd["mood"] == "epic_warrior"
    assert qd["hook"] == "You already know."
    assert qd["flux_prompt"] == "FLUX"
    assert qd["row_number"] == 7
    assert decision.visual_direction.get("caption_marker") == "You already know."
