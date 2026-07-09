import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from studio.types import (
    Concept, Decision, CreativeBrief, PerformanceBrief,
    DECISION_SCHEMA,
)
from studio.settings import ROLE_MODELS, AUDIENCES
from src.core.excel_reader import VALID_MOODS


def test_concept_roundtrip():
    c = Concept(id="c1", angle_label="confront", hook="You already know.",
                caption="long caption", cta="Save this.",
                reel_scenes=["s1", "s2"], hashtags=["#Stoicism"])
    assert Concept.from_dict(c.to_dict()) == c


def test_decision_roundtrip_and_mood_field():
    d = Decision(
        scores=[{"concept_id": "c1", "score": 8, "critique": "strong"}],
        top_pick="c1", alt_pick=None,
        revision={"requested": False, "concept_id": "", "feedback": ""},
        visual_direction={"mood": "epic_warrior", "flux_prompt": "x",
                          "typography": "bold", "palette": "amber"},
        rationale="why")
    d2 = Decision.from_dict(d.to_dict())
    assert d2 == d
    assert d2.visual_direction["mood"] in VALID_MOODS


def test_models_are_exact_ids():
    assert ROLE_MODELS["copywriter"] == "claude-opus-4-8"
    assert ROLE_MODELS["strategist"] == "claude-sonnet-4-6"


def test_audiences_match_renderer():
    assert set(AUDIENCES) == {"procrastinator", "doomscroller", "stuck",
                              "lazy", "quitter", "lost", "overwhelmed"}


def test_decision_schema_is_strict_object():
    assert DECISION_SCHEMA["type"] == "object"
    assert DECISION_SCHEMA["additionalProperties"] is False
