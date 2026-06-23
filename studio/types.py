"""Dataclasses passed between studio agents + JSON schemas for structured output."""
from __future__ import annotations

from dataclasses import dataclass, asdict, field

from excel_reader import VALID_MOODS
from studio.settings import AUDIENCES


@dataclass
class PerformanceBrief:
    generated_at: str
    sample_size: int
    window_days: int
    top_hooks: list = field(default_factory=list)
    top_topics: list = field(default_factory=list)
    top_moods: list = field(default_factory=list)
    best_formats: dict = field(default_factory=dict)
    best_slots: dict = field(default_factory=dict)
    dying: list = field(default_factory=list)
    headline: str = ""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


@dataclass
class CreativeBrief:
    audience: str
    topic_theme: str
    quote: dict
    format: str
    angle: str
    must_include: list
    must_avoid: list
    slot: int
    hypothesis: str

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


@dataclass
class Concept:
    id: str
    angle_label: str
    hook: str
    caption: str
    cta: str
    reel_scenes: list
    hashtags: list

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


@dataclass
class Decision:
    scores: list
    top_pick: str
    alt_pick: str | None
    revision: dict
    visual_direction: dict
    rationale: str

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


def _obj(props, required):
    return {"type": "object", "additionalProperties": False,
            "properties": props, "required": required}


PERFORMANCE_BRIEF_SCHEMA = _obj({
    "generated_at": {"type": "string"},
    "sample_size": {"type": "integer"},
    "window_days": {"type": "integer"},
    "top_hooks": {"type": "array", "items": {"type": "object"}},
    "top_topics": {"type": "array", "items": {"type": "object"}},
    "top_moods": {"type": "array", "items": {"type": "object"}},
    "best_formats": {"type": "object"},
    "best_slots": {"type": "object"},
    "dying": {"type": "array", "items": {"type": "object"}},
    "headline": {"type": "string"},
}, ["generated_at", "sample_size", "window_days", "headline"])

CREATIVE_BRIEF_SCHEMA = _obj({
    "audience": {"type": "string", "enum": list(AUDIENCES)},
    "topic_theme": {"type": "string"},
    "quote": {"type": "object"},
    "format": {"type": "string", "enum": ["reel", "carousel", "image"]},
    "angle": {"type": "string"},
    "must_include": {"type": "array", "items": {"type": "string"}},
    "must_avoid": {"type": "array", "items": {"type": "string"}},
    "slot": {"type": "integer"},
    "hypothesis": {"type": "string"},
}, ["audience", "topic_theme", "quote", "format", "angle", "slot", "hypothesis"])

CONCEPT_SCHEMA = _obj({
    "id": {"type": "string"},
    "angle_label": {"type": "string"},
    "hook": {"type": "string"},
    "caption": {"type": "string"},
    "cta": {"type": "string"},
    "reel_scenes": {"type": "array", "items": {"type": "string"}},
    "hashtags": {"type": "array", "items": {"type": "string"}},
}, ["id", "angle_label", "hook", "caption", "cta", "reel_scenes", "hashtags"])

CONCEPTS_SCHEMA = _obj(
    {"concepts": {"type": "array", "items": CONCEPT_SCHEMA}}, ["concepts"])

DECISION_SCHEMA = _obj({
    "scores": {"type": "array", "items": {"type": "object"}},
    "top_pick": {"type": "string"},
    "alt_pick": {"type": ["string", "null"]},
    "revision": {"type": "object"},
    "visual_direction": _obj({
        "mood": {"type": "string", "enum": list(VALID_MOODS)},
        "flux_prompt": {"type": "string"},
        "typography": {"type": "string"},
        "palette": {"type": "string"},
    }, ["mood", "flux_prompt", "typography", "palette"]),
    "rationale": {"type": "string"},
}, ["scores", "top_pick", "revision", "visual_direction", "rationale"])
