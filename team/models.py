"""Dataclasses for team agent I/O + JSON schemas for structured LLM output.

Mirrors the conventions in studio/types.py: every dataclass gets to_dict/from_dict
classmethods, and every LLM-structured-output call gets a JSON schema built with a
local _obj(props, required) helper (duplicated here rather than imported from
studio/types.py so team/ has no dependency on studio/ internals).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class PostPlan:
    post_number: int
    posting_time: str
    quote_id: int
    audience: str
    mood: str
    format: str
    hook_strategy: str
    visual_style: str
    audio_strategy: str
    engagement_strategy: str
    controversy_question: str
    cta: str
    hashtags: list[str]
    estimated_viral_potential: float
    rationale: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PostPlan":
        return cls(**d)


@dataclass
class ContentPlan:
    date: str
    posts: list[PostPlan]

    def to_dict(self) -> dict:
        return {"date": self.date, "posts": [p.to_dict() for p in self.posts]}

    @classmethod
    def from_dict(cls, d: dict) -> "ContentPlan":
        return cls(date=d["date"], posts=[PostPlan.from_dict(p) for p in d["posts"]])


@dataclass
class DebateResult:
    round_number: int
    planner_output: str       # json.dumps of the ContentPlan that round
    reviewer_output: str      # json.dumps of the reviewer's raw critique dict that round
    reviewer_score: float
    approved: bool
    final_plan: ContentPlan   # nested dataclass — to_dict/from_dict must round-trip it

    def to_dict(self) -> dict:
        return {
            "round_number": self.round_number,
            "planner_output": self.planner_output,
            "reviewer_output": self.reviewer_output,
            "reviewer_score": self.reviewer_score,
            "approved": self.approved,
            "final_plan": self.final_plan.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DebateResult":
        return cls(
            round_number=d["round_number"],
            planner_output=d["planner_output"],
            reviewer_output=d["reviewer_output"],
            reviewer_score=d["reviewer_score"],
            approved=d["approved"],
            final_plan=ContentPlan.from_dict(d["final_plan"]),
        )


@dataclass
class CopySpec:
    post_number: int
    hook: str
    caption: str
    cta: str
    controversy_question: str
    hashtags: list[str]
    carousel_slides: list[str]
    story_teaser: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CopySpec":
        return cls(**d)


@dataclass
class VisualSpec:
    post_number: int
    flux_prompt: str
    composition_params: dict
    wallpaper_design: dict
    carousel_design: list[dict]
    color_palette: dict
    font_choice: dict

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "VisualSpec":
        return cls(**d)


@dataclass
class AudioSpec:
    post_number: int
    music_track: str
    voiceover_text: str
    voiceover_emotion: str
    beat_markers: list[float]
    mix_levels: dict
    jingle: bool

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AudioSpec":
        return cls(**d)


@dataclass
class VideoSpec:
    post_number: int
    scenes: list[dict]
    total_duration: float
    transitions: list[str]
    motion_effects: list[str]
    text_overlays: list[dict]
    aspect_ratio: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "VideoSpec":
        return cls(**d)


@dataclass
class EngagementSpec:
    post_number: int
    seed_comments: list[str]
    reply_templates: list[str]
    dm_trigger: str
    save_bait_frame: str
    story_teaser: str
    highlight_category: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "EngagementSpec":
        return cls(**d)


@dataclass
class AnalyticsReport:
    date: str
    total_posts: int
    avg_engagement_rate: float
    top_performing_hooks: list[str]
    top_performing_moods: list[str]
    best_posting_times: list[str]
    worst_performing_content: list[str]
    recommendations: list[str]
    follower_growth: int
    save_rate: float

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AnalyticsReport":
        return cls(**d)


@dataclass
class VideoQualityScore:
    post_number: int
    visual_appeal: int
    text_readability: int
    content_relevance: int
    production_quality: int
    overall_score: float
    is_acceptable: bool
    feedback: str
    suggestions: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "VideoQualityScore":
        return cls(**d)


@dataclass
class TrendReport:
    niche: str
    hashtags: list[dict]
    sounds: list[dict]
    fetched_at: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TrendReport":
        return cls(**d)


def _obj(props, required):
    return {"type": "object", "additionalProperties": False,
            "properties": props, "required": required}


POST_PLAN_ITEM_SCHEMA = _obj({
    "post_number": {"type": "integer"},
    "posting_time": {"type": "string"},
    "quote_id": {"type": "integer"},
    "audience": {"type": "string"},
    "mood": {"type": "string"},
    "format": {"type": "string"},
    "hook_strategy": {"type": "string"},
    "visual_style": {"type": "string"},
    "audio_strategy": {"type": "string"},
    "engagement_strategy": {"type": "string"},
    "controversy_question": {"type": "string"},
    "cta": {"type": "string"},
    "hashtags": {"type": "array", "items": {"type": "string"}},
    "estimated_viral_potential": {"type": "number"},
    "rationale": {"type": "string"},
}, ["post_number", "posting_time", "quote_id", "audience", "mood", "format",
    "hook_strategy", "visual_style", "audio_strategy", "engagement_strategy",
    "controversy_question", "cta", "hashtags", "estimated_viral_potential",
    "rationale"])

CONTENT_PLAN_SCHEMA = _obj({
    "date": {"type": "string"},
    "posts": {"type": "array", "items": POST_PLAN_ITEM_SCHEMA},
}, ["date", "posts"])

REVIEWER_OUTPUT_SCHEMA = _obj({
    "score": {"type": "number"},
    "approved": {"type": "boolean"},
    "critique": {"type": "string"},
    "strengths": {"type": "array", "items": {"type": "string"}},
    "weaknesses": {"type": "array", "items": {"type": "string"}},
    "improvement_suggestions": {"type": "array", "items": {"type": "string"}},
}, ["score", "approved", "critique", "strengths", "weaknesses",
    "improvement_suggestions"])

COPY_SPEC_ITEM_SCHEMA = _obj({
    "post_number": {"type": "integer"},
    "hook": {"type": "string"},
    "caption": {"type": "string"},
    "cta": {"type": "string"},
    "controversy_question": {"type": "string"},
    "hashtags": {"type": "array", "items": {"type": "string"}},
    "carousel_slides": {"type": "array", "items": {"type": "string"}},
    "story_teaser": {"type": "string"},
}, ["post_number", "hook", "caption", "cta", "controversy_question", "hashtags",
    "carousel_slides", "story_teaser"])

COPY_SPECS_SCHEMA = _obj(
    {"items": {"type": "array", "items": COPY_SPEC_ITEM_SCHEMA}}, ["items"])

VISUAL_SPEC_ITEM_SCHEMA = _obj({
    "post_number": {"type": "integer"},
    "flux_prompt": {"type": "string"},
    "composition_params": {"type": "object"},
    "wallpaper_design": {"type": "object"},
    "carousel_design": {"type": "array", "items": {"type": "object"}},
    "color_palette": {"type": "object"},
    "font_choice": {"type": "object"},
}, ["post_number", "flux_prompt", "composition_params", "wallpaper_design",
    "carousel_design", "color_palette", "font_choice"])

VISUAL_SPECS_SCHEMA = _obj(
    {"items": {"type": "array", "items": VISUAL_SPEC_ITEM_SCHEMA}}, ["items"])

AUDIO_SPEC_ITEM_SCHEMA = _obj({
    "post_number": {"type": "integer"},
    "music_track": {"type": "string"},
    "voiceover_text": {"type": "string"},
    "voiceover_emotion": {"type": "string"},
    "beat_markers": {"type": "array", "items": {"type": "number"}},
    "mix_levels": {"type": "object"},
    "jingle": {"type": "boolean"},
}, ["post_number", "music_track", "voiceover_text", "voiceover_emotion",
    "beat_markers", "mix_levels", "jingle"])

AUDIO_SPECS_SCHEMA = _obj(
    {"items": {"type": "array", "items": AUDIO_SPEC_ITEM_SCHEMA}}, ["items"])

VIDEO_SPEC_ITEM_SCHEMA = _obj({
    "post_number": {"type": "integer"},
    "scenes": {"type": "array", "items": {"type": "object"}},
    "total_duration": {"type": "number"},
    "transitions": {"type": "array", "items": {"type": "string"}},
    "motion_effects": {"type": "array", "items": {"type": "string"}},
    "text_overlays": {"type": "array", "items": {"type": "object"}},
    "aspect_ratio": {"type": "string"},
}, ["post_number", "scenes", "total_duration", "transitions", "motion_effects",
    "text_overlays", "aspect_ratio"])

VIDEO_SPECS_SCHEMA = _obj(
    {"items": {"type": "array", "items": VIDEO_SPEC_ITEM_SCHEMA}}, ["items"])

ENGAGEMENT_SPEC_ITEM_SCHEMA = _obj({
    "post_number": {"type": "integer"},
    "seed_comments": {"type": "array", "items": {"type": "string"}},
    "reply_templates": {"type": "array", "items": {"type": "string"}},
    "dm_trigger": {"type": "string"},
    "save_bait_frame": {"type": "string"},
    "story_teaser": {"type": "string"},
    "highlight_category": {"type": "string"},
}, ["post_number", "seed_comments", "reply_templates", "dm_trigger",
    "save_bait_frame", "story_teaser", "highlight_category"])

ENGAGEMENT_SPECS_SCHEMA = _obj(
    {"items": {"type": "array", "items": ENGAGEMENT_SPEC_ITEM_SCHEMA}}, ["items"])

ANALYTICS_REPORT_SCHEMA = _obj({
    "date": {"type": "string"},
    "total_posts": {"type": "integer"},
    "avg_engagement_rate": {"type": "number"},
    "top_performing_hooks": {"type": "array", "items": {"type": "string"}},
    "top_performing_moods": {"type": "array", "items": {"type": "string"}},
    "best_posting_times": {"type": "array", "items": {"type": "string"}},
    "worst_performing_content": {"type": "array", "items": {"type": "string"}},
    "recommendations": {"type": "array", "items": {"type": "string"}},
    "follower_growth": {"type": "integer"},
    "save_rate": {"type": "number"},
}, ["date", "total_posts", "avg_engagement_rate", "top_performing_hooks",
    "top_performing_moods", "best_posting_times", "worst_performing_content",
    "recommendations", "follower_growth", "save_rate"])

VIDEO_QUALITY_SCORE_ITEM_SCHEMA = _obj({
    "post_number": {"type": "integer"},
    "visual_appeal": {"type": "integer"},
    "text_readability": {"type": "integer"},
    "content_relevance": {"type": "integer"},
    "production_quality": {"type": "integer"},
    "overall_score": {"type": "number"},
    "is_acceptable": {"type": "boolean"},
    "feedback": {"type": "string"},
    "suggestions": {"type": "string"},
}, ["post_number", "visual_appeal", "text_readability", "content_relevance",
    "production_quality", "overall_score", "is_acceptable", "feedback", "suggestions"])

VIDEO_QUALITY_SCORES_SCHEMA = _obj(
    {"items": {"type": "array", "items": VIDEO_QUALITY_SCORE_ITEM_SCHEMA}}, ["items"])
