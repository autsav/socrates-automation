"""Dataclasses passed between studio agents + JSON schemas for structured output."""
from __future__ import annotations

from dataclasses import dataclass, asdict, field

from src.core.excel_reader import VALID_MOODS
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


@dataclass
class MusicDirection:
    search_query: str
    energy: str
    bpm_range: list
    instruments: list
    avoid: list

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


@dataclass
class MusicPick:
    track_id: str
    rationale: str
    runner_up_id: str | None = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


@dataclass
class TrendHook:
    used: bool
    topic: str = ""
    source: str = ""
    hook: str = ""
    bridge: str = ""
    rationale: str = ""

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
    "top_hooks": {"type": "array", "items": _obj(
        {"hook": {"type": "string"}, "lift": {"type": "number"}}, ["hook", "lift"])},
    "top_topics": {"type": "array", "items": _obj(
        {"topic": {"type": "string"}, "lift": {"type": "number"}}, ["topic", "lift"])},
    "top_moods": {"type": "array", "items": _obj(
        {"mood": {"type": "string"}, "lift": {"type": "number"}}, ["mood", "lift"])},
    "best_formats": _obj(
        {"reel": {"type": "number"}, "carousel": {"type": "number"}, "image": {"type": "number"}}, []),
    "best_slots": _obj(
        {"morning": {"type": "number"}, "lunch": {"type": "number"}, "evening": {"type": "number"}}, []),
    "dying": {"type": "array", "items": _obj(
        {"pattern": {"type": "string"}, "reason": {"type": "string"}}, ["pattern", "reason"])},
    "headline": {"type": "string"},
}, ["generated_at", "sample_size", "window_days", "headline"])

CREATIVE_BRIEF_SCHEMA = _obj({
    "audience": {"type": "string", "enum": list(AUDIENCES)},
    "topic_theme": {"type": "string"},
    "quote": _obj({
        "row_number": {"type": ["integer", "null"]},
        "text": {"type": "string"},
        "author": {"type": "string"},
        "source": {"type": "string"},
        "need_new": {"type": "boolean"},
        "theme": {"type": "string"},
    }, []),
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
    "scores": {"type": "array", "items": _obj(
        {"concept_id": {"type": "string"}, "score": {"type": "number"}, "note": {"type": "string"}},
        ["concept_id", "score"])},
    "top_pick": {"type": "string"},
    "alt_pick": {"type": ["string", "null"]},
    "revision": _obj({
        "requested": {"type": "boolean"},
        "concept_id": {"type": "string"},
        "feedback": {"type": "string"},
    }, ["requested"]),
    "visual_direction": _obj({
        "mood": {"type": "string", "enum": list(VALID_MOODS)},
        "flux_prompt": {"type": "string"},
        "typography": {"type": "string"},
        "palette": {"type": "string"},
    }, ["mood", "flux_prompt", "typography", "palette"]),
    "rationale": {"type": "string"},
}, ["scores", "top_pick", "revision", "visual_direction", "rationale"])

MUSIC_DIRECTION_SCHEMA = _obj({
    "search_query": {"type": "string"},
    "energy": {"type": "string", "enum": ["low", "medium", "high"]},
    "bpm_range": {"type": "array", "items": {"type": "integer"}},
    "instruments": {"type": "array", "items": {"type": "string"}},
    "avoid": {"type": "array", "items": {"type": "string"}},
}, ["search_query", "energy", "bpm_range", "instruments", "avoid"])

MUSIC_PICK_SCHEMA = _obj({
    "track_id": {"type": "string"},
    "rationale": {"type": "string"},
    "runner_up_id": {"type": ["string", "null"]},
}, ["track_id", "rationale"])

TREND_HOOK_SCHEMA = _obj({
    "used": {"type": "boolean"},
    "topic": {"type": "string"},
    "source": {"type": "string"},
    "hook": {"type": "string"},
    "bridge": {"type": "string"},
    "rationale": {"type": "string"},
}, ["used"])


@dataclass
class QuoteData:
    hook: str
    bridge: str | None
    quote: str
    cta: str
    caption: str
    hashtags: list
    mood: str
    attribution: str
    audience: str
    row_number: int | None
    music_track_id: str | None = None
    flux_prompt: str | None = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


QUOTE_DATA_SCHEMA = _obj({
    "hook": {"type": "string"},
    "bridge": {"type": ["string", "null"]},
    "quote": {"type": "string"},
    "cta": {"type": "string"},
    "caption": {"type": "string"},
    "hashtags": {"type": "array", "items": {"type": "string"},
                 "minItems": 3, "maxItems": 5},
    "mood": {"type": "string", "enum": list(VALID_MOODS)},
    "attribution": {"type": "string"},
    "audience": {"type": "string"},
    "row_number": {"type": ["integer", "null"]},
    "music_track_id": {"type": ["string", "null"]},
    "flux_prompt": {"type": ["string", "null"]},
}, ["hook", "quote", "cta", "caption", "hashtags", "mood",
    "attribution", "audience", "row_number"])
