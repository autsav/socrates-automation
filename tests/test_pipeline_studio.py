import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import pipeline
import studio.run as studio_run
import studio.client as studio_client
from studio.client import StudioError
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
    assert qd["topic_theme"] == "fear"
    assert qd["angle"] == "confront"


def test_apply_studio_decision_raises_on_unknown_top_pick():
    """A hallucinated top_pick id must raise a catchable StudioError, not a
    bare KeyError, so pipeline.py's fallback wrapper can catch it."""
    brief = CreativeBrief("stuck", "fear", {"row_number": 7, "text": "Know thyself"},
                          "reel", "confront", [], [], 0, "x")
    decision = Decision(
        [{"concept_id": "c1", "score": 9, "critique": "ok"}], "c2-does-not-exist", None,
        {"requested": False, "concept_id": "", "feedback": ""},
        {"mood": "epic_warrior", "flux_prompt": "FLUX", "typography": "b", "palette": "amber"},
        "rationale")
    concepts = {"c1": Concept("c1", "a", "hook", "cap", "cta", ["s"], ["#h"])}
    with pytest.raises(StudioError):
        pipeline._apply_studio_decision(brief, decision, concepts)


def test_studio_stage_falls_back_when_quote_unresolvable(monkeypatch):
    """If the strategist asked for need_new (or an unmatched row_number) and
    no text is resolvable, _studio_stage must signal fallback (None) instead
    of shipping an empty quote."""
    brief = CreativeBrief("stuck", "fear", {"need_new": True, "theme": "grit"},
                          "reel", "confront", [], [], 0, "x")
    decision = Decision(
        [{"concept_id": "c1", "score": 9, "critique": "ok"}], "c1", None,
        {"requested": False, "concept_id": "", "feedback": ""},
        {"mood": "epic_warrior", "flux_prompt": "FLUX", "typography": "b", "palette": "amber"},
        "rationale")
    concepts = {"c1": Concept("c1", "a", "hook", "cap", "cta", ["s"], ["#h"])}

    monkeypatch.setattr(studio_run, "_build_pool", lambda path: [])
    monkeypatch.setattr(studio_run, "run_studio",
                        lambda client, slot, pool, recent: (brief, decision, concepts))
    monkeypatch.setattr(studio_client, "StudioClient", lambda key: object())

    class _Cfg:
        ANTHROPIC_API_KEY = "key"

    assert pipeline._studio_stage(_Cfg(), 0) is None
